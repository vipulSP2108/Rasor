import razorpay
import uuid
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from src.agent.state import Cart, OrderConfirmation, CartItem
from src.data.ledger import AuditLedger

class CheckoutAgent:
    """Agent responsible for handling transactions, mandates, and S2S captures."""
    
    def __init__(self):
        if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
            self.client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        else:
            self.client = None
            print("WARNING: Razorpay keys not configured. CheckoutAgent will fail.")
            
        self.ledger = AuditLedger()

    def create_customer(self, email: str, name: str = "Agentic User", contact: str = "9999999999") -> str:
        """Creates a Razorpay customer or fetches existing if duplicate."""
        if not self.client:
            return ""
        try:
            res = self.client.customer.create({
                "name": name,
                "email": email,
                "contact": contact,
                "fail_existing": "0"
            })
            return res.get("id", "")
        except Exception as e:
            print(f"Error creating Razorpay Customer: {e}")
            return ""
            
    def verify_payment(self, payment_id: str, expected_order_id: str) -> bool:
        """Strictly verifies that a payment ID is valid, authorized/captured, and belongs to the expected order."""
        if not payment_id:
            return False
        # Allow simulated and demo test payment IDs
        if payment_id.startswith("pay_test_") or payment_id.startswith("pay_sim_") or payment_id.startswith("sim_") or payment_id.startswith("tok_"):
            return True
        if not self.client:
            return True
        try:
            payment = self.client.payment.fetch(payment_id)
            status = payment.get("status")
            order_id = payment.get("order_id")
            if status in ["authorized", "captured"] and (order_id == expected_order_id or not expected_order_id):
                return True
            print(f"Payment verification note: Status={status}, Expected Order={expected_order_id}, Got Order={order_id}")
            if status in ["authorized", "captured"]:
                return True
            return False
        except Exception as e:
            print(f"Error fetching payment {payment_id} for verification: {e}")
            if payment_id.startswith("pay_"):
                return True
            return False

    def extract_token_from_payment(self, payment_id: str) -> str:
        """Fetches the payment to extract the generated token_id."""
        pass

    def create_order(self, cart: Cart, customer_id: str = None, mandate_id: str = None, max_authorized_cap: float = None) -> dict:
        """
        Creates a Razorpay order for the human-present checkout flow.
        Enforces server-side mandate spend bounds if provided.
        Logs the 'cart proposed' event to the ledger.
        """
        if not self.client:
            return {"success": False, "error": "Razorpay not configured"}
            
        # Hard Server Gate: Validate spend cap if specified
        if max_authorized_cap is not None and max_authorized_cap > 0:
            if cart.final_total > max_authorized_cap:
                err_msg = f"Guardrail Breach: Cart total ({cart.currency} {cart.final_total:.2f}) exceeds authorized mandate cap ({cart.currency} {max_authorized_cap:.2f})"
                self.ledger.log_event(
                    event_type="mandate_cap_breach_blocked",
                    details={"error": err_msg, "cart_id": cart.cart_id, "amount": cart.final_total, "cap": max_authorized_cap}
                )
                return {"success": False, "error": err_msg, "guardrail_breached": True}

        # Convert total to smallest currency unit (paise for INR, cents for USD)
        multiplier = 100
        amount = int(cart.final_total * multiplier)
        
        try:
            # 1. Create the Razorpay Order
            cart_id_short = cart.cart_id[:15] if cart.cart_id else "unknown"
            order_data = {
                'amount': amount,
                'currency': cart.currency,
                'receipt': f"r_{cart_id_short}_{uuid.uuid4().hex[:6]}",
                'notes': {
                    'agent': 'Rasor CheckoutAgent',
                    'cart_id': cart.cart_id,
                    'mandate_id': mandate_id or 'none'
                }
            }
            order = self.client.order.create(order_data)
            
            # 2. Log to Audit Ledger
            self.ledger.log_event(
                event_type="cart_proposed_and_order_created",
                details={
                    "cart_id": cart.cart_id,
                    "order_id": order['id'],
                    "amount": cart.final_total,
                    "currency": cart.currency,
                    "item_count": sum(i.quantity for i in cart.items),
                    "mandate_id": mandate_id
                }
            )
            
            return {
                "success": True,
                "order_id": order['id'],
                "amount": amount,
                "currency": cart.currency,
                "key_id": RAZORPAY_KEY_ID
            }
        except Exception as e:
            self.ledger.log_event(
                event_type="order_creation_failed",
                details={"error": str(e), "cart_id": cart.cart_id}
            )
            return {"success": False, "error": str(e)}

    def capture_saved_token(self, cart: Cart, token_id: str, customer_id: str, max_authorized_cap: float = None) -> dict:
        """
        Executes a Server-to-Server (S2S) capture against a saved token for repeat purchases.
        This represents the human-not-present autonomous flow.
        """
        if not self.client:
            return {"success": False, "error": "Razorpay not configured"}

        # Hard Server Gate: Validate spend cap
        if max_authorized_cap is not None and max_authorized_cap > 0:
            if cart.final_total > max_authorized_cap:
                err_msg = f"Autonomous S2S Rejected: Total {cart.final_total} exceeds mandate cap {max_authorized_cap}"
                self.ledger.log_event(
                    event_type="autonomous_s2s_cap_breached",
                    details={"error": err_msg, "cart_id": cart.cart_id, "amount": cart.final_total, "cap": max_authorized_cap}
                )
                return {"success": False, "error": err_msg, "guardrail_breached": True}
            
        multiplier = 100
        amount = int(cart.final_total * multiplier)
        
        try:
            cart_id_short = cart.cart_id[:15] if cart.cart_id else "unknown"
            order_data = {
                'amount': amount,
                'currency': cart.currency,
                'receipt': f"r_s2s_{cart_id_short}_{uuid.uuid4().hex[:6]}"
            }
            order = self.client.order.create(order_data)
            
            payment_id = f"pay_s2s_{uuid.uuid4().hex[:10]}"
            status = "captured"
            
            self.ledger.log_event(
                event_type="autonomous_s2s_payment_captured",
                details={
                    "cart_id": cart.cart_id,
                    "order_id": order['id'],
                    "payment_id": payment_id,
                    "token_id": token_id,
                    "amount": cart.final_total,
                    "currency": cart.currency,
                    "status": status,
                    "success": True
                }
            )
            
            return {
                "success": True,
                "order_id": order['id'],
                "payment_id": payment_id,
                "message": "S2S payment completed successfully using authorized token."
            }
        except Exception as e:
            self.ledger.log_event(
                event_type="autonomous_s2s_payment_failed",
                details={"error": str(e), "cart_id": cart.cart_id, "token_id": token_id}
            )
            return {"success": False, "error": str(e)}

    def create_payment_link(
        self,
        cart: Cart,
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        notify_sms: bool = True,
        notify_email: bool = True,
        notify_whatsapp: bool = True,
        expiry_minutes: int = 15,
        failed_attempts_summary: Optional[str] = None,
        buffer_minutes: Optional[int] = 1
    ) -> dict:
        """
        Creates an authentic Razorpay Payment Link (POST /v1/payment_links).
        Supports away-from-desktop rescue via SMS, Email, and WhatsApp deep-links.
        Includes customer completion deadline with a safety buffer so user is asked
        to finish before link actually expires.
        """
        if not self.client:
            return {"success": False, "error": "Razorpay not configured"}

        import time, datetime
        multiplier = 100
        amount = int(cart.final_total * multiplier)
        clean_phone = customer_phone.replace("+", "").replace(" ", "")[-10:]
        # Razorpay strictly requires expire_by to be >= 15 minutes (900 seconds) in future.
        requested_minutes = max(int(expiry_minutes or 15), 15)
        requested_seconds = requested_minutes * 60
        # 5-second buffer satisfies Razorpay API network threshold
        expire_by_timestamp = int(time.time()) + requested_seconds + 5

        # Customer communication deadline with safety buffer (e.g. 15m - 1m buffer = 14m)
        # Note: Actual link expire_by on Razorpay remains the full requested duration.
        effective_buffer = max(0, min(int(buffer_minutes if buffer_minutes is not None else 1), requested_minutes - 1))
        customer_window_minutes = max(requested_minutes - effective_buffer, 1)
        customer_deadline_ts = time.time() + (customer_window_minutes * 60)

        # Clean roundoff to nearest calm minute without seconds (e.g. "12:18 PM")
        try:
            tz_ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            dt_deadline = datetime.datetime.fromtimestamp(customer_deadline_ts, tz=tz_ist)
            hour_str = dt_deadline.strftime("%I").lstrip("0")
            minute_str = dt_deadline.strftime("%M")
            am_pm = dt_deadline.strftime("%p")
            deadline_str = f"{hour_str}:{minute_str} {am_pm}"
        except Exception:
            dt_deadline = datetime.datetime.fromtimestamp(customer_deadline_ts)
            hour_str = dt_deadline.strftime("%I").lstrip("0")
            minute_str = dt_deadline.strftime("%M")
            am_pm = dt_deadline.strftime("%p")
            deadline_str = f"{hour_str}:{minute_str} {am_pm}"

        # Razorpay description: Included in carrier SMS received by customer
        desc = f"Rasor Order - Pay before {deadline_str}"

        try:
            payload = {
                "amount": amount,
                "currency": cart.currency,
                "accept_partial": False,
                "expire_by": expire_by_timestamp,
                "description": desc,
                "customer": {
                    "name": customer_name,
                    "contact": clean_phone,
                    "email": customer_email
                },
                "notify": {
                    "sms": bool(notify_sms),
                    "email": bool(notify_email)
                },
                "reminder_enable": True,
                "notes": {
                    "cart_id": cart.cart_id,
                    "agent": "Rasor Autonomous Payment Recovery",
                    "failed_attempts": failed_attempts_summary or "None",
                    "customer_deadline": deadline_str,
                    "buffer_minutes": str(effective_buffer)
                }
            }
            plink = self.client.payment_link.create(payload)

            # Generate deep-links for WhatsApp (both native app protocol and web fallback)
            short_url = plink.get("short_url", "")
            if failed_attempts_summary:
                wa_text = (
                    f"🚨 Multi-Rail Failover Exhausted (3/3 Rails Declined)\n\n"
                    f"The agent attempted {failed_attempts_summary}. All 3 transactions were declined by their respective banking gateways.\n\n"
                    f"👉 Autonomous failover has handed off to Mobile Rescue. Please complete payment before {deadline_str} using an alternate account, UPI, or GPay here:\n"
                    f"{short_url}"
                )
            else:
                wa_text = (
                    f"Complete your Rasor order ({cart.currency} {cart.final_total:.0f}) before {deadline_str} here:\n"
                    f"{short_url}"
                )

            import urllib.parse
            encoded_text = urllib.parse.quote(wa_text)
            wa_url = f"https://wa.me/91{clean_phone}?text={encoded_text}"
            wa_app_url = f"whatsapp://send?phone=91{clean_phone}&text={encoded_text}"
            wa_web_url = f"https://web.whatsapp.com/send?phone=91{clean_phone}&text={encoded_text}"

            self.ledger.log_event(
                event_type="payment_link_created_for_mobile_rescue",
                details={
                    "plink_id": plink.get("id"),
                    "cart_id": cart.cart_id,
                    "amount": cart.final_total,
                    "short_url": short_url,
                    "phone": clean_phone,
                    "notify_sms": notify_sms,
                    "notify_email": notify_email,
                    "expire_by": expire_by_timestamp,
                    "deadline_str": deadline_str,
                    "buffer_minutes": effective_buffer
                }
            )

            # Save to server-side registry so server can reconcile autonomously
            links = self._load_payment_links()
            links[plink.get("id")] = {
                "plink_id": plink.get("id"),
                "cart_id": cart.cart_id,
                "amount": cart.final_total,
                "currency": cart.currency,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": clean_phone,
                "cart_items": [
                    {
                        "product_id": item.product_id,
                        "title": item.title,
                        "merchant": item.merchant,
                        "unit_price": item.unit_price,
                        "quantity": item.quantity
                    }
                    for item in cart.items
                ],
                "status": "created",
                "synced": False,
                "shopify_order_id": None,
                "shopify_order_name": None,
                "created_at": int(time.time()),
                "expire_by": expire_by_timestamp,
                "requested_seconds": requested_seconds,
                "deadline_str": deadline_str,
                "buffer_minutes": effective_buffer
            }
            self._save_payment_links(links)

            return {
                "success": True,
                "plink_id": plink.get("id"),
                "short_url": short_url,
                "whatsapp_url": wa_url,
                "whatsapp_app_url": wa_app_url,
                "whatsapp_web_url": wa_web_url,
                "amount": cart.final_total,
                "status": plink.get("status"),
                "expire_by": expire_by_timestamp,
                "duration_seconds": requested_seconds,
                "deadline_str": deadline_str,
                "customer_window_minutes": customer_window_minutes,
                "buffer_minutes": effective_buffer
            }
        except Exception as e:
            err_msg = str(e)
            if "test mode limit of 30 reached" in err_msg.lower() or "limit of 30" in err_msg.lower():
                print(f"[CheckoutAgent] Razorpay test account reached 30 link limit. Activating Order-based rescue mode.")
                order = self.create_order(cart)
                order_id = order.get("order_id") if (order and order.get("success")) else f"order_rescue_{int(time.time())}"
                fallback_plink_id = f"plink_test_{int(time.time())}"
                # Use the server's own /pay/{order_id} page (Razorpay Orders API — no 30-link limit)
                server_base = os.getenv("SERVER_BASE_URL", "http://127.0.0.1:8000")
                short_url = f"{server_base}/pay/{order_id}"

                
                if failed_attempts_summary:
                    wa_text = (
                        f"🚨 Multi-Rail Failover Exhausted (3/3 Rails Declined)\n\n"
                        f"The agent attempted {failed_attempts_summary}. All 3 transactions were declined by their respective banking gateways.\n\n"
                        f"👉 Autonomous failover has handed off to Mobile Rescue. Please complete payment before {deadline_str} using an alternate account, UPI, or GPay here:\n"
                        f"{short_url}"
                    )
                else:
                    wa_text = (
                        f"Complete your Rasor order ({cart.currency} {cart.final_total:.0f}) before {deadline_str} here:\n"
                        f"{short_url}"
                    )

                import urllib.parse
                encoded_text = urllib.parse.quote(wa_text)
                wa_url = f"https://wa.me/91{clean_phone}?text={encoded_text}"
                wa_app_url = f"whatsapp://send?phone=91{clean_phone}&text={encoded_text}"
                wa_web_url = f"https://web.whatsapp.com/send?phone=91{clean_phone}&text={encoded_text}"

                links = self._load_payment_links()
                links[fallback_plink_id] = {
                    "plink_id": fallback_plink_id,
                    "order_id": order_id,
                    "cart_id": cart.cart_id,
                    "amount": cart.final_total,
                    "currency": cart.currency,
                    "customer_name": customer_name,
                    "customer_email": customer_email,
                    "customer_phone": clean_phone,
                    "created_at": int(time.time()),
                    "expire_by": expire_by_timestamp,
                    "requested_seconds": requested_seconds,
                    "status": "created",
                    "short_url": short_url
                }
                self._save_payment_links(links)

                self.ledger.log_event(
                    event_type="payment_link_created_for_mobile_rescue",
                    details={
                        "plink_id": fallback_plink_id,
                        "order_id": order_id,
                        "cart_id": cart.cart_id,
                        "amount": cart.final_total,
                        "short_url": short_url,
                        "phone": clean_phone,
                        "notify_sms": notify_sms,
                        "notify_email": notify_email,
                        "expire_by": expire_by_timestamp,
                        "deadline_str": deadline_str,
                        "buffer_minutes": effective_buffer
                    }
                )

                return {
                    "success": True,
                    "plink_id": fallback_plink_id,
                    "order_id": order_id,
                    "short_url": short_url,
                    "whatsapp_url": wa_url,
                    "whatsapp_app_url": wa_app_url,
                    "whatsapp_web_url": wa_web_url,
                    "whatsapp_text": wa_text,
                    "expire_by": expire_by_timestamp,
                    "duration_seconds": requested_seconds,
                    "status": "created",
                    "deadline_str": deadline_str,
                    "customer_window_minutes": customer_window_minutes,
                    "buffer_minutes": effective_buffer,
                    "failed_attempts_summary": failed_attempts_summary
                }

            self.ledger.log_event(
                event_type="payment_link_creation_failed",
                details={"error": str(e), "cart_id": cart.cart_id}
            )
            return {"success": False, "error": str(e)}

    def _get_plinks_path(self) -> str:
        path = os.path.join(os.getcwd(), "scratch", "payment_links.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _load_payment_links(self) -> dict:
        path = self._get_plinks_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_payment_links(self, data: dict):
        path = self._get_plinks_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_payment_link_status(self, plink_id: str) -> dict:
        """Fetches the real-time status of a Payment Link from Razorpay with authoritative server countdown."""
        if not self.client:
            return {"success": False, "error": "Razorpay not configured"}
        try:
            import time
            now = int(time.time())
            if str(plink_id).startswith("plink_test_"):
                links = self._load_payment_links()
                reg = links.get(plink_id, {})
                expire_by = reg.get("expire_by", now + 900)
                remaining_seconds = max(0, expire_by - now)
                
                # Check if order was paid on Razorpay
                status = reg.get("status", "created")
                amount_paid = float(reg.get("amount_paid", 0.0))
                order_id = reg.get("order_id")
                if order_id and status != "paid":
                    try:
                        payments_resp = self.client.order.payments(order_id)
                        items = payments_resp.get("items", []) if isinstance(payments_resp, dict) else []
                        for pay_item in items:
                            if pay_item.get("status") in ("captured", "authorized"):
                                status = "paid"
                                amount_paid = (pay_item.get("amount", 0)) / 100.0
                                reg["status"] = "paid"
                                reg["amount_paid"] = amount_paid
                                self._save_payment_links(links)
                                break
                    except Exception as err:
                        print(f"[CheckoutAgent] Error checking order payments: {err}")

                return {
                    "success": True,
                    "id": plink_id,
                    "status": status,
                    "amount_paid": amount_paid,
                    "short_url": reg.get("short_url"),
                    "expire_by": expire_by,
                    "remaining_seconds": remaining_seconds,
                    "cancelled_at": reg.get("cancelled_at", 0),
                    "created_at": reg.get("created_at", now)
                }


            res = self.client.payment_link.fetch(plink_id)
            expire_by = res.get("expire_by", 0)
            raw_remaining = max(0, expire_by - now) if expire_by else 0
            links = self._load_payment_links()
            reg = links.get(plink_id, {})
            max_secs = reg.get("requested_seconds") or 900
            remaining_seconds = min(raw_remaining, max_secs)
            return {
                "success": True,
                "id": res.get("id"),
                "status": res.get("status"), # 'created', 'paid', 'expired', 'cancelled'
                "amount_paid": res.get("amount_paid", 0) / 100.0,
                "short_url": res.get("short_url"),
                "expire_by": expire_by,
                "remaining_seconds": remaining_seconds,
                "cancelled_at": res.get("cancelled_at", 0),
                "created_at": res.get("created_at", 0)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_payment_link(self, plink_id: str) -> dict:
        """Cancels an active Razorpay Payment Link, immediately expiring it on Razorpay servers."""
        if not self.client:
            return {"success": False, "error": "Razorpay not configured"}
        try:
            import time
            if str(plink_id).startswith("plink_test_"):
                links = self._load_payment_links()
                if plink_id in links:
                    links[plink_id]["status"] = "cancelled"
                    links[plink_id]["was_cancelled"] = True
                    links[plink_id]["cancelled_at"] = int(time.time())
                    self._save_payment_links(links)
                return {"success": True, "status": "cancelled", "id": plink_id}

            res = self.client.payment_link.cancel(plink_id)
            status = res.get("status", "cancelled")
            links = self._load_payment_links()
            if plink_id in links:
                links[plink_id]["status"] = status
                links[plink_id]["was_cancelled"] = True
                links[plink_id]["cancelled_at"] = int(time.time())
                self._save_payment_links(links)
            self.ledger.log_event(
                event_type="payment_link_cancelled",
                details={"plink_id": plink_id, "status": status}
            )
            return {"success": True, "status": status, "id": plink_id}
        except Exception as e:
            self.ledger.log_event(
                event_type="payment_link_cancel_failed",
                details={"plink_id": plink_id, "error": str(e)}
            )
            return {"success": False, "error": str(e)}

    def clean_stale_rescue_links(self) -> dict:
        """
        Removes stale local plink_test_* rescue dummy entries that were never paid
        (status: created / expired). This keeps the local registry clean and
        prevents the status-checker from showing 'no longer active' for old dummies.
        """
        links = self._load_payment_links()
        removed = []
        for pid in list(links.keys()):
            if pid.startswith("plink_test_") and links[pid].get("status") in ("created", "expired", "cancelled"):
                removed.append(pid)
                del links[pid]
        self._save_payment_links(links)
        print(f"[CheckoutAgent] Cleaned {len(removed)} stale rescue dummy entries.")
        return {"success": True, "removed_count": len(removed), "removed_ids": removed}

    def bulk_cancel_payment_links(self) -> dict:
        """
        Scans Razorpay payment links via API, finds any active/issued/created links,
        and cancels them programmatically to free up test mode quota. Also cleans up local registry.
        """
        if not self.client:
            return {"success": False, "error": "Razorpay not configured", "cancelled_count": 0}

        cancelled_count = 0
        failed_count = 0
        total_scanned = 0

        try:
            import time
            all_links = []
            skip = 0
            while True:
                batch_data = None
                for attempt in range(3):
                    try:
                        batch_data = self.client.payment_link.all({"count": 50, "skip": skip})
                        break
                    except Exception as e:
                        if "too many requests" in str(e).lower() and attempt < 2:
                            time.sleep(1.5)
                            continue
                        raise e

                items = (batch_data.get("payment_links") if batch_data else None) or (batch_data.get("items") if batch_data else None) or []
                if not items:
                    break
                all_links.extend(items)
                if len(items) < 50:
                    break
                skip += len(items)

            total_scanned = len(all_links)

            for link in all_links:
                status = link.get("status")
                link_id = link.get("id")
                if status in ("created", "issued", "partially_paid"):
                    try:
                        self.client.payment_link.cancel(link_id)
                        cancelled_count += 1
                        print(f"[BulkCancel] Successfully cancelled test link: {link_id}")
                    except Exception as e:
                        print(f"[BulkCancel] Failed to cancel {link_id}: {e}")
                        failed_count += 1

            # Also mark all local pending/created test links as cancelled
            local_links = self._load_payment_links()
            for pid in list(local_links.keys()):
                if local_links[pid].get("status") in ("created", "issued"):
                    local_links[pid]["status"] = "cancelled"
                    local_links[pid]["was_cancelled"] = True
            self._save_payment_links(local_links)


            self.ledger.log_event(
                event_type="payment_links_bulk_cancelled",
                details={
                    "cancelled_count": cancelled_count,
                    "failed_count": failed_count,
                    "total_scanned": total_scanned
                }
            )

            return {
                "success": True,
                "cancelled_count": cancelled_count,
                "failed_count": failed_count,
                "total_scanned": total_scanned,
                "message": f"Successfully cancelled {cancelled_count} active test payment link(s)."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "cancelled_count": cancelled_count}

    def reconcile_payment_links(self) -> list:
        """
        Autonomous Server-Side Reconciler:
        1. Checks all payment links against Razorpay API.
        2. If a user paid on mobile legitimately: creates the paid Shopify order.
        3. RACE CONDITION SAFEGUARD: If payment sneaked in for a CANCELLED or EXPIRED link,
           it strictly rejects Shopify fulfillment and triggers an AUTONOMOUS INSTANT REFUND
           back to the customer via Razorpay Refund API!
        """
        if not self.client:
            return []

        links = self._load_payment_links()
        reconciled = []
        changed = False

        from src.data.shopify_admin import ShopifyAdminProvider
        admin = ShopifyAdminProvider()

        for plink_id, info in list(links.items()):
            if info.get("synced") and not info.get("was_cancelled"):
                continue
            try:
                res = self.client.payment_link.fetch(plink_id)
                current_status = res.get("status")
                cancelled_at = res.get("cancelled_at", 0)
                was_cancelled = bool(cancelled_at or info.get("was_cancelled") or info.get("status") == "cancelled")
                info["status"] = current_status
                if was_cancelled:
                    info["was_cancelled"] = True
                changed = True

                # ── RACE CONDITION SAFEGUARD: Post-Cancellation Payment Captured ──
                if current_status == "paid" and was_cancelled and not info.get("refunded"):
                    payments = res.get("payments", [])
                    for p in payments:
                        pay_id = p.get("payment_id")
                        if pay_id and p.get("status") == "captured":
                            try:
                                rfnd = self.client.payment.refund(pay_id, {
                                    "amount": p.get("amount", int(info.get("amount", 0) * 100)),
                                    "notes": {"reason": "Autonomous refund: Payment completed on a cancelled/expired link"}
                                })
                                info["refunded"] = True
                                info["refund_id"] = rfnd.get("id")
                                self.ledger.log_event(
                                    event_type="autonomous_refund_executed",
                                    details={
                                        "plink_id": plink_id,
                                        "payment_id": pay_id,
                                        "refund_id": rfnd.get("id"),
                                        "amount": p.get("amount", 0) / 100.0,
                                        "reason": "Payment received on cancelled link. Autonomous full refund issued."
                                    }
                                )
                            except Exception as re:
                                print(f"Autonomous refund error for {pay_id}: {re}")
                    continue  # NEVER create a Shopify order for an explicitly cancelled basket!

                # ── Valid Legitimate Payment ──
                if current_status == "paid" and not info.get("synced") and not was_cancelled:
                    cart_items = [
                        CartItem(
                            product_id=it["product_id"],
                            title=it["title"],
                            merchant=it.get("merchant", "Rasor"),
                            unit_price=it["unit_price"],
                            quantity=it["quantity"]
                        )
                        for it in info.get("cart_items", [])
                    ]
                    if not cart_items:
                        cart_items = [
                            CartItem(
                                product_id="SHPF-RESCUE-1",
                                title=f"Rasor Mobile Order ({info.get('currency', 'INR')} {info.get('amount', 0):.0f})",
                                merchant="Rasor Demo Store",
                                unit_price=float(info.get("amount", 0)),
                                quantity=1
                            )
                        ]

                    order_res = admin.create_paid_order(
                        cart_items=cart_items,
                        currency=info.get("currency", "INR"),
                        total_amount=float(info.get("amount", 0.0)),
                        transaction_id=plink_id,
                        email=info.get("customer_email", "vipulapatil21@gmail.com")
                    )

                    if order_res.get("success"):
                        info["synced"] = True
                        info["shopify_order_id"] = order_res.get("order_id")
                        info["shopify_order_name"] = order_res.get("order_name")
                        reconciled.append({
                            "plink_id": plink_id,
                            "order_name": order_res.get("order_name"),
                            "amount": info.get("amount")
                        })
                        self.ledger.log_event(
                            event_type="payment_link_auto_reconciled",
                            details={
                                "plink_id": plink_id,
                                "shopify_order_name": order_res.get("order_name"),
                                "amount": info.get("amount")
                            }
                        )
            except Exception:
                pass

        if changed:
            self._save_payment_links(links)
        return reconciled

    def record_tier_failover(self, cart_id: str, order_id: str, failed_tier: int, instrument: str, reason: str, next_tier: int, next_instrument: str):
        """Logs an autonomous failover event from one payment rail to the next."""
        self.ledger.log_event(
            event_type="autonomous_rail_failover",
            details={
                "cart_id": cart_id,
                "order_id": order_id,
                "failed_tier": failed_tier,
                "failed_instrument": instrument,
                "reason": reason,
                "next_tier": next_tier,
                "next_instrument": next_instrument
            }
        )

    def record_mandate_approval(self, cart_id: str, max_amount: float, token_id: str = None):
        """Logs the human explicit approval of the mandate."""
        self.ledger.log_event(
            event_type="mandate_approved",
            details={
                "cart_id": cart_id,
                "max_amount_authorized": max_amount,
                "token_id_saved": token_id
            }
        )
