"""Generate the SYNTHETIC raw dataset used in the Week 2 data-readiness homework.

Track: Customer Support Assistant.
Company "ShopNova" is fictional. No real person, customer, payment or company data is used.
Emails use the reserved example.com domain; phone numbers are fake; the card number is the
public test number 4111 1111 1111 1111.

The generator is deterministic (fixed seed). It is run ONCE to create data/raw/. The processing
pipeline never calls it and never writes to data/raw/.

Defects are injected on purpose so that the readiness pipeline has something real to diagnose:
duplicates, empty text, missing group keys, invalid / future timestamps, mixed timestamp formats,
inconsistent categories and labels, missing labels (more often on Mondays), PII, payment data,
out-of-scope language, extreme lengths, impossible handle times, stale / draft / duplicate
knowledge articles.

Usage:  python -m src.data.generate_synthetic_data      (from the Week2 folder)
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 2026
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
LOCAL_TZ = timezone(timedelta(hours=7))

# --------------------------------------------------------------------------- knowledge base
KB_ARTICLES = [
    dict(kb_id="KB-001", title="Return policy", category="return_policy", owner="Policy Team",
         approved="true", last_reviewed="2026-05-12", version="3.1",
         body="""Customers can return most items within 30 days of delivery.
The item must be unused and in its original packaging. Final-sale items, gift cards and
personalised products cannot be returned.

To start a return, the customer opens the order page, selects "Return item" and prints the
prepaid label. Returns are free for orders shipped within Vietnam. After the parcel reaches the
warehouse, inspection takes up to 3 business days.

If the item arrived damaged, the customer should send a photo within 48 hours of delivery so the
agent can create a damage claim instead of a normal return."""),
    dict(kb_id="KB-002", title="Refund timeline", category="refund_status", owner="Finance Ops",
         approved="true", last_reviewed="2026-06-20", version="2.4",
         body="""Refunds are issued after the returned item passes inspection.
Card refunds take 5 to 10 business days to appear, depending on the bank. E-wallet refunds take
1 to 3 business days. Store-credit refunds are available immediately after approval.

Agents can check the refund status on the order page. If the refund was approved more than
10 business days ago and the customer still has not received it, escalate to Finance Ops with
the order number. Agents must never ask the customer for full card details."""),
    dict(kb_id="KB-003", title="Delivery times", category="delivery_time", owner="Logistics",
         approved="true", last_reviewed="2026-07-02", version="4.0",
         body="""Standard delivery takes 2 to 4 business days in Hanoi and Ho Chi Minh City
and 3 to 6 business days in other provinces. Express delivery takes 1 to 2 business days in
major cities.

Orders placed after 15:00 local time are processed on the next business day. Public holidays
are not business days. A tracking number is sent by email once the parcel leaves the warehouse.

If a parcel has not moved for more than 3 business days, the agent opens a carrier
investigation from the order page."""),
    dict(kb_id="KB-004", title="Warranty claims", category="warranty_claim", owner="Policy Team",
         approved="true", last_reviewed="2026-04-28", version="1.8",
         body="""Electronics sold by ShopNova carry a 12-month warranty from the delivery
date. The warranty covers manufacturing defects. It does not cover accidental damage, water
damage or normal wear.

To make a claim, the customer provides the order number, a short description of the fault and
a photo or video. The agent creates a warranty case. The repair centre replies within
5 business days with a repair, replacement or refund decision."""),
    dict(kb_id="KB-005", title="Change or cancel an order", category="order_change",
         owner="Customer Support", approved="true", last_reviewed="2026-08-03", version="2.0",
         body="""An order can be changed or cancelled free of charge until it is packed.
The order page shows the status "Packing" once this is no longer possible.

Address changes after packing require a carrier redirect request, which is not guaranteed.
If an order cannot be cancelled, the customer can refuse delivery or use the normal return
process after delivery."""),
    dict(kb_id="KB-006", title="Account access and password reset", category="account_access",
         owner="Customer Support", approved="true", last_reviewed="2026-06-15", version="1.5",
         body="""Customers reset their password from the "Forgot password" link on the
sign-in page. The reset link is valid for 30 minutes.

If the customer no longer has access to the registered email address, the agent must verify
the account with the last order number and the delivery postcode before updating the email.
Agents never send passwords and never ask for a one-time code."""),
    dict(kb_id="KB-007", title="Payment failures and double charges", category="payment_issue",
         owner="Finance Ops", approved="true", last_reviewed="2026-07-21", version="2.2",
         body="""A failed payment does not create an order. A temporary authorisation may
appear on the customer's statement and is released by the bank within 7 business days.

If the customer reports a double charge, the agent checks the order page for two paid orders.
If only one order exists, the second amount is an authorisation hold. If two paid orders exist,
the agent cancels the duplicate and the refund timeline in KB-002 applies. Never ask the
customer to send card numbers in chat or email."""),
    dict(kb_id="KB-008", title="Shipping fees", category="delivery_time", owner="Logistics",
         approved="true", last_reviewed="2026-07-02", version="1.3",
         body="""Standard delivery is free for orders above 500,000 VND. Below that amount
the standard fee is 30,000 VND. Express delivery costs 60,000 VND for all orders.

Shipping fees are refunded only when the whole order is returned because of a ShopNova error,
such as a wrong or damaged item."""),
    dict(kb_id="KB-009", title="Damaged items", category="return_policy", owner="Policy Team",
         approved="true", last_reviewed="2026-05-30", version="1.0",
         body="   "),  # extraction failure: empty body
    dict(kb_id="KB-010", title="Gift cards", category="other", owner="Customer Support",
         approved="true", last_reviewed="2026-03-18", version="1.1",
         body="""Gift cards are valid for 24 months from purchase and can be used for any
product on ShopNova. They cannot be exchanged for cash or returned.

A lost gift card code can be re-sent to the purchaser's email address from the order page."""),
    dict(kb_id="KB-011", title="Delivery times (copy)", category="delivery_time", owner="Logistics",
         approved="true", last_reviewed="2026-07-02", version="4.0",
         body=None),  # exact duplicate of KB-003 body, filled below
    dict(kb_id="KB-012", title="Warranty extension programme", category="warranty_claim",
         owner="Policy Team", approved="true", last_reviewed="2024-11-05", version="1.0",
         body="""Customers can buy a 12-month warranty extension within 30 days of delivery
for selected electronics. The extension price is 10 percent of the product price.

Extension claims follow the same process as normal warranty claims."""),
    dict(kb_id="KB-013", title="DRAFT - new refund policy", category="refund_status",
         owner="Finance Ops", approved="false", last_reviewed="2026-09-10", version="0.3",
         body="""DRAFT - not approved. Proposal: card refunds within 3 business days for
members. Do not use with customers until approved by Finance Ops."""),
    dict(kb_id="KB-014", title="Order tracking", category="delivery_time", owner="",
         approved="true", last_reviewed="2026-06-01", version="1.2",
         body="""The tracking number appears on the order page and in the shipping email.
Tracking updates can take up to 24 hours after the parcel leaves the warehouse. Customers can
also track the parcel on the carrier's website with the same number."""),
]

# --------------------------------------------------------------------------- tickets
CUSTOMER_TEMPLATES = {
    "return_policy": [
        "Hi, I want to return the shoes from order {order}. They do not fit. How do I do it?",
        "Can I still return an item I received {days} days ago? Order {order}.",
        "The jacket in order {order} is not what I expected. Is the return free?",
        "How long do I have to send back a product? I bought it last week ({order}).",
    ],
    "refund_status": [
        "I returned order {order} two weeks ago and I still have no refund. Where is my money?",
        "When will I get my refund for {order}? The return was accepted on Monday.",
        "My refund for order {order} is not on my card yet. How long does it take?",
        "Refund for {order} still missing, it has been {days} days.",
    ],
    "delivery_time": [
        "When will order {order} arrive? I live in Da Nang.",
        "My parcel {order} has not moved for 4 days. Is something wrong?",
        "How long does express delivery take to Hanoi? Asking about {order}.",
        "Order {order} was supposed to arrive yesterday. Any update?",
    ],
    "warranty_claim": [
        "My headphones from order {order} stopped working after 3 months. Is this covered?",
        "The laptop charger from {order} is broken. How do I make a warranty claim?",
        "Screen flickers on the tablet I bought ({order}). What can I do?",
    ],
    "order_change": [
        "Can I change the delivery address for order {order}? I just placed it.",
        "Please cancel order {order}, I ordered the wrong size.",
        "I want to add one more item to {order}. Is that possible?",
    ],
    "account_access": [
        "I cannot log in to my account. The reset link does not work.",
        "I lost access to my old email. How can I update my account email?",
        "Password reset email never arrives. Please help.",
    ],
    "payment_issue": [
        "I was charged twice for order {order}. Please check.",
        "Payment failed but money left my account. Order {order}.",
        "Why is there a pending charge on my statement? I cancelled {order}.",
    ],
    "other": [
        "Do gift cards expire? I received one as a present.",
        "I lost my gift card code. Can you send it again?",
    ],
}
AGENT_TEMPLATES = {
    "return_policy": "Thanks for reaching out. Items can be returned within 30 days of delivery if unused and in original packaging. Open the order page, choose Return item and print the free label.",
    "refund_status": "I checked order {order}. The return passed inspection and the refund was approved. Card refunds take 5 to 10 business days depending on your bank.",
    "delivery_time": "Standard delivery takes 3 to 6 business days outside Hanoi and Ho Chi Minh City. I have checked {order} and the parcel is with the carrier.",
    "warranty_claim": "Electronics have a 12-month warranty for manufacturing defects. Please send a short description and a photo or video and I will create a warranty case.",
    "order_change": "Order {order} has not been packed yet, so I have updated it for you. You will receive a confirmation email.",
    "account_access": "Please use the Forgot password link on the sign-in page. The link is valid for 30 minutes. For an email change I need your last order number and delivery postcode.",
    "payment_issue": "I can see only one paid order. The second amount is a temporary authorisation that your bank releases within 7 business days.",
    "other": "Gift cards are valid for 24 months. I have re-sent the code to the purchaser's email address.",
}
FOLLOW_UPS = [
    "Thank you, that helps.",
    "OK. And what if it takes longer than that?",
    "Got it, thanks!",
    "Can you confirm the address on the order?",
    "Still nothing after a week, please check again.",
]
AGENT_FOLLOW_UP = "Thanks for the update. I have added a note to the ticket and will follow up by email."

VIETNAMESE = [
    "Chào shop, đơn hàng {order} của tôi bao giờ được giao ạ?",
    "Tôi muốn đổi trả sản phẩm trong đơn {order}, làm thế nào?",
    "Tại sao tôi bị trừ tiền hai lần cho đơn {order}?",
    "Mật khẩu của tôi không đặt lại được, giúp tôi với.",
    "Hoàn tiền đơn {order} mất bao lâu vậy?",
]

INTENT_WEIGHTS = {
    "delivery_time": 0.24, "refund_status": 0.20, "return_policy": 0.16, "payment_issue": 0.11,
    "order_change": 0.10, "account_access": 0.08, "warranty_claim": 0.07, "other": 0.04,
}
LABEL_VARIANTS = {
    "return_policy": ["return_policy", "Return Policy", "returns"],
    "refund_status": ["refund_status", "Refund", "refund-status", "REFUND"],
    "delivery_time": ["delivery_time", "Delivery", "shipping_delay", "delivery time"],
    "warranty_claim": ["warranty_claim", "Warranty"],
    "order_change": ["order_change", "Order Change", "cancel_order"],
    "account_access": ["account_access", "Login", "password_reset"],
    "payment_issue": ["payment_issue", "Payment", "double_charge"],
    "other": ["other", "Other", "gift_card"],
}
CHANNEL_VARIANTS = {
    "email": ["email", "Email", "E-mail", "EMAIL"],
    "chat": ["chat", "Chat", "CHAT", "live_chat"],
    "web_form": ["web_form", "Web Form", "webform"],
}

FIELDS = ["message_id", "ticket_id", "created_at", "channel", "customer_ref", "sender_role",
          "message_text", "intent_label", "resolution_status", "csat_score", "resolved_at",
          "handle_time_min"]


def fmt_ts(rng: random.Random, dt_local: datetime) -> str:
    """Mixed timestamp formats, as found in many helpdesk exports."""
    r = rng.random()
    if r < 0.60:
        return dt_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if r < 0.85:
        return dt_local.isoformat(timespec="seconds")          # +07:00 offset
    return dt_local.strftime("%Y-%m-%d %H:%M:%S")               # naive local time (UTC+07)


def make_tickets(rng: random.Random) -> list[dict]:
    start = datetime(2026, 6, 1, 8, 0, tzinfo=LOCAL_TZ)
    span_days = 120  # 1 Jun 2026 -> 28 Sep 2026
    rows: list[dict] = []
    msg_no = 0
    intents = list(INTENT_WEIGHTS)
    weights = [INTENT_WEIGHTS[i] for i in intents]

    def next_id() -> str:
        nonlocal msg_no
        msg_no += 1
        return f"MSG-{msg_no:06d}"

    for t in range(230):
        ticket_id = f"TCK-{10001 + t}"
        intent = rng.choices(intents, weights)[0]
        day = rng.randrange(span_days)
        t0 = start + timedelta(days=day, minutes=rng.randrange(0, 12 * 60))
        order = f"ORD-{rng.randrange(40000, 99999)}"
        cust = f"CUST-{rng.randrange(1000, 9999)}"
        channel_key = rng.choices(["email", "chat", "web_form"], [0.45, 0.40, 0.15])[0]
        channel = rng.choice(CHANNEL_VARIANTS[channel_key])

        # ticket-level outcome fields (post-outcome: must never be used as evidence/features)
        status = rng.choices(["resolved", "pending", "escalated"], [0.82, 0.10, 0.08])[0]
        handle = round(max(2.0, rng.lognormvariate(2.55, 0.45)), 1)  # median ~ 12.8 min
        csat = ""
        if status == "resolved" and rng.random() < 0.48:
            csat = str(rng.choices([1, 2, 3, 4, 5], [0.05, 0.07, 0.15, 0.33, 0.40])[0])
        elif status != "resolved" and rng.random() < 0.15:
            csat = str(rng.choices([1, 2, 3], [0.5, 0.3, 0.2])[0])

        # customer opening message
        text = rng.choice(CUSTOMER_TEMPLATES[intent]).format(order=order, days=rng.randrange(5, 40))
        if rng.random() < 0.11:
            text += rng.choice([
                f" You can reach me at {cust.lower().replace('-', '')}@example.com.",
                f" My phone is 09{rng.randrange(10, 99)} {rng.randrange(100, 999)} {rng.randrange(100, 999)}.",
            ])
        label = rng.choice(LABEL_VARIANTS[intent])
        p_missing = 0.20 if t0.weekday() == 0 else 0.05   # Mondays: higher queue load
        if rng.random() < p_missing:
            label = ""

        msgs = [("customer", t0, text, label)]
        t1 = t0 + timedelta(minutes=rng.randrange(5, 240))
        msgs.append(("agent", t1, AGENT_TEMPLATES[intent].format(order=order), ""))
        if rng.random() < 0.50:
            t2 = t1 + timedelta(minutes=rng.randrange(10, 600))
            msgs.append(("customer", t2, rng.choice(FOLLOW_UPS), ""))
            t3 = t2 + timedelta(minutes=rng.randrange(5, 300))
            msgs.append(("agent", t3, AGENT_FOLLOW_UP, ""))
        last = msgs[-1][1]
        resolved_at = ""
        if status == "resolved":
            resolved_at = (last + timedelta(minutes=rng.randrange(1, 120))).astimezone(
                timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for role, ts, body, lab in msgs:
            rows.append(dict(
                message_id=next_id(), ticket_id=ticket_id, created_at=fmt_ts(rng, ts),
                channel=channel, customer_ref=cust, sender_role=role, message_text=body,
                intent_label=lab, resolution_status=status, csat_score=csat,
                resolved_at=resolved_at, handle_time_min=str(handle),
                _intent=intent, _order=order, _ts=ts))
    return rows


def inject_defects(rng: random.Random, rows: list[dict]) -> list[dict]:
    cust_first = [r for r in rows if r["sender_role"] == "customer" and r["intent_label"] != ""]
    rng.shuffle(cust_first)
    pick = iter(cust_first)

    # payment data in text (critical privacy defect)
    for _ in range(3):
        r = next(pick)
        r["message_text"] = (f"I was charged twice for {r['_order']}. My card is 4111 1111 1111 1111, "
                             "please refund the second payment.")
    # out-of-scope language (MVP is English only)
    for i in range(5):
        r = next(pick)
        r["message_text"] = VIETNAMESE[i].format(order=r["_order"])
    # unmapped labels
    for bad in ["misc??", "TBD", "see notes", "urgent"]:
        next(pick)["intent_label"] = bad
    # extreme length: pasted email chains / logs
    for _ in range(4):
        r = next(pick)
        chain = ("-----Original message-----\nFrom: ShopNova <noreply@shopnova.example>\n"
                 "Subject: Your order update\nYour parcel is on its way. Track it on the order page.\n")
        r["message_text"] = r["message_text"] + "\n" + chain * rng.randrange(30, 60)

    others = [r for r in rows if r["sender_role"] in ("customer", "agent")]
    rng.shuffle(others)
    pool = iter(others)
    for _ in range(6):                      # empty text
        next(pool)["message_text"] = rng.choice(["", "   ", "\n"])
    for _ in range(4):                      # missing group key
        next(pool)["ticket_id"] = ""
    for bad in ["31/02/2026 10:00", "N/A", "2026-13-05T10:00:00Z", "yesterday", "0000-00-00 00:00:00"]:
        next(pool)["created_at"] = bad      # invalid timestamp
    for bad in ["2027-01-15T09:30:00Z", "2026-11-02T10:00:00+07:00"]:
        next(pool)["created_at"] = bad      # future timestamp (after export snapshot)

    # impossible / extreme handle times (ticket level)
    tickets = sorted({r["ticket_id"] for r in rows if r["ticket_id"]})
    special = rng.sample(tickets, 8)
    values = ["0", "0", "0", "-3", "-12.5", "640", "715", "980"]
    for tid, v in zip(special, values):
        for r in rows:
            if r["ticket_id"] == tid:
                r["handle_time_min"] = v

    # near duplicates: customer re-sends the same message 30 s later with a new message_id
    firsts = [r for r in rows if r["sender_role"] == "customer" and r["message_text"].strip()
              and len(r["message_text"]) < 400 and r["ticket_id"]]
    extra = []
    msg_no = max(int(r["message_id"].split("-")[1]) for r in rows)
    for r in rng.sample(firsts, 6):
        msg_no += 1
        c = dict(r)
        c["message_id"] = f"MSG-{msg_no:06d}"
        c["message_text"] = "  " + r["message_text"].upper() + " "
        c["created_at"] = (r["_ts"] + timedelta(seconds=30)).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        c["intent_label"] = ""
        extra.append(c)
    rows.extend(extra)

    # exact duplicate rows (export glitch): identical in every field
    dups = [dict(r) for r in rng.sample(rows, 12)]
    rows.extend(dups)
    return rows


def main() -> None:
    rng = random.Random(SEED)
    kb_dir = RAW / "knowledge_base"
    kb_dir.mkdir(parents=True, exist_ok=True)
    kb3 = next(a for a in KB_ARTICLES if a["kb_id"] == "KB-003")["body"]
    for a in KB_ARTICLES:
        body = kb3 if a["body"] is None else a["body"]
        front = "\n".join(f"{k}: {a[k]}" for k in
                          ["kb_id", "title", "category", "owner", "approved", "last_reviewed", "version"])
        (kb_dir / f"{a['kb_id']}.md").write_text(f"---\n{front}\n---\n{body}\n", encoding="utf-8")

    rows = inject_defects(rng, make_tickets(rng))
    out = RAW / "tickets" / "tickets_export_2026-09-30.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(KB_ARTICLES)} KB articles and {len(rows)} ticket messages")


if __name__ == "__main__":
    main()
