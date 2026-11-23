"""
legal_content.py — Canonical legal-page templates (privacy / terms / refund).

WHY THIS EXISTS
───────────────
Google Play rejected "Bibek Pro" and "Palei Pro" (Aug 30, 2026) under the
Privacy Policy section of the User Data policy:

    "Missing data disclosure — Your privacy policy does not disclose the
     access or collection of Location."

The websites used to hardcode their legal copy inside each Next.js page, so a
policy fix meant a code change + redeploy on every site, and the two brands
drifted apart. Legal copy is now *data*: it lives in `domain_legal_pages`,
is editable from Admin Dashboard → Domains → Legal, and is rendered by the
websites via `/domains/{id}/legal/{page_key}`.

This module holds the DEFAULT template used to seed a domain that has no legal
rows yet (and to power the admin "Restore default template" button). The text
is deliberately parameterised by domain so the SAME backend image, deployed
twice on the VPS (Bibek Enterprises + Palei Solutions), produces correct,
brand-specific policies from one source of truth.

The privacy template discloses every permission actually present in the merged
Android manifests of the four apps in this repo:
  - ACCESS_FINE_LOCATION / ACCESS_COARSE_LOCATION / ACCESS_BACKGROUND_LOCATION
    / FOREGROUND_SERVICE_LOCATION  → §3 "Location Information"
  - CAMERA                          → §4 "Camera, Photos & Signatures"
  - POST_NOTIFICATIONS + FCM token  → §5 "Device & Technical Information"
  - Razorpay / UPI                  → §6 "Payment Information"
Keep §3–§6 in sync with the manifests whenever a permission is added.
"""
from __future__ import annotations

from typing import Any

# Page keys the system knows about. Order = display order in the admin UI.
LEGAL_PAGE_KEYS: tuple[str, ...] = ("privacy", "terms", "refund-policy")

# Human labels for the admin UI / API responses.
LEGAL_PAGE_LABELS: dict[str, str] = {
    "privacy":       "Privacy Policy",
    "terms":         "Terms of Service",
    "refund-policy": "Refund & Cancellation Policy",
}


def build_context(
    *,
    site_name: str,
    legal_name: str | None = None,
    support_email: str | None = None,
    support_phone: str | None = None,
    address: str | None = None,
    gstin: str | None = None,
    website: str | None = None,
    updated: str = "September 2026",
) -> dict[str, Any]:
    """Normalise the domain-specific values interpolated into the templates."""
    legal = legal_name or site_name
    email = support_email or "support@example.com"
    phone = support_phone or "+91 00000 00000"
    where = f"{legal}, {address}" if address else legal
    return {
        "site_name":  site_name,
        "legal_name": legal,
        "email":      email,
        "phone":      phone,
        "address":    address or "",
        "gstin":      gstin or "",
        "website":    website or "",
        "updated":    updated,
        "who":        where,
    }


# ══════════════════════════════════════════════════════════════════════════
# PRIVACY POLICY
# ══════════════════════════════════════════════════════════════════════════
def _privacy_sections(c: dict[str, Any]) -> list[dict[str, str]]:
    site = c["site_name"]
    return [
        {
            "id": "scope",
            "title": "1. Scope of This Policy",
            "content": (
                f"This Privacy Policy explains how {c['legal_name']} (“{site}”, "
                "“we”, “us”) collects, uses, shares and protects your "
                "information. It applies to our website, our customer mobile app, and our "
                "technician/partner mobile app (published on Google Play as a separate "
                "“Pro” app for field staff). Where a practice applies to only one "
                "of these, we say so explicitly. By using any of them you agree to this "
                "policy. We are the data fiduciary/controller for the data described below."
            ),
        },
        {
            "id": "info-we-collect",
            "title": "2. Information You Give Us",
            "content": (
                "Customers: your name, mobile number, email address, service address "
                "(house/flat, street, landmark, city, PIN code), the appliance and problem "
                "details you describe, preferred slot, coupon codes, and any messages you "
                "send our support team. Technicians and partner staff: additionally your "
                "date of birth, government ID and address-proof documents, PAN, bank "
                "account or UPI details for payouts, employment/skill details, and "
                "emergency contact. We do not collect caste, religion, biometric data, "
                "health data, or any other special-category data."
            ),
        },
        # ── THE SECTION GOOGLE PLAY SAID WAS MISSING. Do not delete. ──
        {
            "id": "location",
            "title": "3. Location Information",
            "content": (
                "We collect and use location data as follows.\n\n"
                "(a) Customer app and website — approximate and precise location. With "
                "your permission we read your device location once, while the app is in "
                "use, so we can pre-fill your service address, show you the correct city "
                "and pricing, and confirm that your address falls inside a serviceable "
                "area. You can skip this and type your address manually; only the address "
                "you confirm is stored.\n\n"
                "(b) Technician / partner app — precise location, collected in the "
                "foreground AND in the background. When a technician switches their "
                "status to “Online” or accepts a job, the app collects precise GPS "
                "location continuously — including while the app is minimised, the screen "
                "is off, or the app is closed — using an Android foreground service with "
                "a persistent notification. We use this location only to: (i) route the "
                "nearest available technician to a booking; (ii) show the customer live "
                "“technician on the way” tracking and ETA; (iii) verify on-site arrival, "
                "check-in/check-out and attendance; (iv) reconstruct the visit trail if a "
                "job, payment or safety incident is disputed. Background location "
                "collection starts only after the technician grants the “Allow all the "
                "time” permission and goes Online, and it stops as soon as they go "
                "Offline, revoke the permission in Android Settings, or log out. It is "
                "never collected from a technician who is Offline.\n\n"
                "(c) What we do NOT do with location. We do not sell or rent location "
                "data. We do not share it with advertisers, data brokers or analytics "
                "networks. We do not use it to build advertising profiles, and we do not "
                "track technicians outside their working/Online hours.\n\n"
                "(d) Retention. Live location pings are retained for 90 days for support, "
                "billing and dispute resolution and are then deleted or aggregated into "
                "non-identifying route statistics. The service address you confirm is "
                "retained with the booking record (see §9)."
            ),
        },
        {
            "id": "camera-photos",
            "title": "4. Camera, Photos & Signatures",
            "content": (
                "The technician app uses the device CAMERA to capture job-site photos "
                "(appliance condition before/after service, spare parts replaced, "
                "meter/serial readings) and to capture the customer’s on-screen signature "
                "as proof of job completion. These images are uploaded to our servers and "
                "attached to the booking record. The customer app may use the camera so "
                "you can attach a photo of the fault when raising a booking. Our apps "
                "capture images with the camera or, where you choose an existing image, "
                "through the Android system photo picker — we do not request broad "
                "photo/media library permissions and we cannot browse, read or index the "
                "other photos and videos on your device."
            ),
        },
        {
            "id": "device-info",
            "title": "5. Device & Technical Information",
            "content": (
                "When you use our website or apps we automatically collect: IP address, "
                "browser type and version, device model, operating-system version, app "
                "version, language, time zone, referring page, pages/screens viewed, and "
                "crash and diagnostic logs. Our apps register a Firebase Cloud Messaging "
                "(FCM) push token so we can deliver booking alerts, job assignments and "
                "OTP/status notifications; this token identifies the app installation, not "
                "you personally, and is deleted when you log out or uninstall. On the "
                "technician app we also record battery-optimisation and notification "
                "permission state, because a technician whose alerts are blocked cannot be "
                "assigned jobs."
            ),
        },
        {
            "id": "payments",
            "title": "6. Payment Information",
            "content": (
                "Online payments are processed by our PCI-DSS compliant payment partners "
                "(Razorpay and UPI apps). Card numbers, CVV, UPI PINs and net-banking "
                "credentials are entered on the payment partner’s interface and are never "
                "seen or stored by us. We store only the transaction reference, amount, "
                "method, status and timestamp so we can issue invoices, process refunds "
                "and meet GST record-keeping obligations. For technician payouts we store "
                "the bank account/UPI details the technician provides, restricted to "
                "finance staff."
            ),
        },
        {
            "id": "how-we-use",
            "title": "7. How We Use Your Information",
            "content": (
                "We use the information above to: (a) create and secure your account, and "
                "verify you by OTP; (b) schedule, dispatch, track and complete the service "
                "you booked; (c) send booking confirmations, technician-assigned and "
                "on-the-way alerts, service reminders and support replies by push "
                "notification, SMS, WhatsApp and email; (d) take payment, generate GST "
                "invoices and process refunds; (e) calculate technician commission, "
                "attendance and payouts; (f) provide customer support and resolve "
                "disputes, complaints and warranty claims; (g) detect and prevent fraud, "
                "misuse and safety incidents; (h) measure and improve service quality and "
                "app reliability; and (i) comply with tax, accounting and other legal "
                "obligations. We do not use your data for automated decision-making that "
                "has a legal or similarly significant effect on you, and we do not sell "
                "your personal data."
            ),
        },
        {
            "id": "sharing",
            "title": "8. Sharing & Disclosure",
            "content": (
                "We share the minimum necessary data with: (a) the assigned technician — "
                "your name, service address, mobile number and fault description, so they "
                "can reach you and do the job; (b) the customer — the assigned "
                "technician’s name, photo, mobile number and live location while the job "
                "is active; (c) payment processors (Razorpay, UPI partners) for the "
                "transaction; (d) communication providers (SMS, WhatsApp Business and "
                "email gateways) to deliver notifications; (e) Google Firebase for push "
                "delivery and crash reporting, and Google Maps for geocoding, routing and "
                "map display; (f) our chartered accountant and statutory auditors for GST "
                "and tax filings; (g) law-enforcement or regulators where we are legally "
                "required to, and where we are permitted we will tell you first. If our "
                "business is merged, acquired or restructured, data may transfer to the "
                "successor entity under this same policy. We never sell or rent your data "
                "and we do not share it with advertising networks."
            ),
        },
        {
            "id": "retention",
            "title": "9. Data Retention",
            "content": (
                "Account and profile data are kept while your account is active. Booking, "
                "invoice, payment and GST records are retained for 8 financial years as "
                "required by Indian tax and company law. Job photos and signatures are kept "
                "for 2 years to support warranty and dispute claims. Live location pings "
                "are kept for 90 days (see §3d). Support conversations are kept for 2 "
                "years. Push tokens and session tokens are deleted on logout. After the "
                "applicable period, data is deleted or irreversibly anonymised."
            ),
        },
        {
            "id": "deletion",
            "title": "10. Account & Data Deletion",
            "content": (
                f"You can ask us to delete your account and personal data at any time by "
                f"emailing {c['email']} from your registered email address, or by calling "
                f"{c['phone']}, with the subject “Delete my account”. We verify the request, "
                "then delete your profile, addresses, push tokens, photos and location "
                "history within 30 days, and confirm by email. We must retain invoice, "
                "payment and GST records for the statutory period in §9 even after deletion "
                "— these are locked down and no longer used to contact you. Deleting your "
                "account cancels any open bookings."
            ),
        },
        {
            "id": "security",
            "title": "11. Data Security",
            "content": (
                "All traffic between our apps, our websites and our servers is encrypted "
                "in transit with HTTPS/TLS. Passwords and MPINs are stored only as salted "
                "one-way hashes — we cannot read them. Access to customer data is "
                "role-based and limited to staff who need it; technicians see only their "
                "own assigned jobs. Databases and backups sit on access-controlled private "
                "servers. No system is perfectly secure, so we cannot guarantee absolute "
                "security, but if a breach affects your personal data we will notify you "
                "and the relevant authority as required by law."
            ),
        },
        {
            "id": "your-rights",
            "title": "12. Your Rights & Choices",
            "content": (
                "You may: (a) access a copy of the personal data we hold about you; "
                "(b) correct anything inaccurate — most fields are editable in the app; "
                "(c) request deletion (see §10); (d) withdraw consent for optional "
                "processing; (e) opt out of promotional SMS/WhatsApp/email at any time "
                "(transactional messages about a live booking will continue); and "
                "(f) revoke any Android permission — location, camera, notifications — in "
                "Settings → Apps → Permissions, or in-app for technicians by going "
                "Offline. Revoking location will stop job assignment on the technician app "
                "and address auto-fill on the customer app, but nothing else breaks. To "
                f"exercise a right, contact {c['email']}; we respond within 15 business days."
            ),
        },
        {
            "id": "cookies",
            "title": "13. Cookies & Analytics",
            "content": (
                "Our website uses strictly-necessary cookies to keep you logged in and to "
                "remember your selected city, plus aggregate analytics to understand which "
                "pages and services are popular. Analytics data is aggregated and is not "
                "used to build advertising profiles. You can block cookies in your browser; "
                "if you do, your login and city preference will not persist. Our mobile "
                "apps do not use advertising IDs and contain no ad SDKs."
            ),
        },
        {
            "id": "children",
            "title": "14. Children’s Privacy",
            "content": (
                "Our services are intended for users aged 18 and above. We do not knowingly "
                "collect personal data from children. If you believe a child has given us "
                "personal data, contact us and we will delete it promptly."
            ),
        },
        {
            "id": "changes",
            "title": "15. Changes to This Policy",
            "content": (
                "We may update this policy to reflect changes in our services, technology "
                "or the law. Material changes — especially any change to what data we "
                "collect or why — will be announced by in-app notice or email at least 14 "
                "days before they take effect. The “Last updated” date at the top of this "
                "page always reflects the version in force. Continuing to use the service "
                "after that date means you accept the updated policy."
            ),
        },
        {
            "id": "contact",
            "title": "16. Contact & Grievance Officer",
            "content": (
                "For any privacy question, data-access or deletion request, or to complain "
                f"about how we handled your data, contact our Grievance Officer at "
                f"{c['who']}. Email: {c['email']} · Phone: {c['phone']}. We acknowledge "
                "every grievance within 48 hours and resolve it within 30 days, as required "
                "by the Information Technology (Reasonable Security Practices) Rules and "
                "the Digital Personal Data Protection Act, 2023."
            ),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════
# TERMS OF SERVICE
# ══════════════════════════════════════════════════════════════════════════
def _terms_sections(c: dict[str, Any]) -> list[dict[str, str]]:
    site = c["site_name"]
    gst_line = f" Our GSTIN is {c['gstin']}." if c["gstin"] else ""
    return [
        {
            "id": "acceptance",
            "title": "1. Acceptance of Terms",
            "content": (
                f"These Terms govern your use of the {site} website and mobile apps and any "
                f"service you book through them. They form a binding agreement between you "
                f"and {c['legal_name']}.{gst_line} By creating an account, booking a service "
                "or using our apps you confirm you are at least 18 years old and accept "
                "these Terms and our Privacy Policy. If you do not agree, do not use the "
                "service."
            ),
        },
        {
            "id": "our-role",
            "title": "2. What We Do",
            "content": (
                f"{site} provides home-appliance repair, installation, servicing and "
                "related maintenance through employed and empanelled technicians. We are "
                "responsible for the work our technicians perform on our behalf. Manufacturer "
                "warranties on the appliance itself remain with the manufacturer; our own "
                "workmanship warranty is described in §7."
            ),
        },
        {
            "id": "account",
            "title": "3. Your Account",
            "content": (
                "You register with a mobile number verified by OTP. Keep your device, OTP "
                "and MPIN confidential — activity from your account is treated as yours. "
                "Give us accurate contact and address details; we are not responsible for a "
                "failed visit caused by a wrong address or an unreachable number. Tell us "
                "immediately if you suspect unauthorised use. We may suspend an account for "
                "fraud, abuse of staff, repeated no-shows or breach of these Terms."
            ),
        },
        {
            "id": "bookings",
            "title": "4. Bookings, Slots & Visits",
            "content": (
                "A booking is confirmed when you receive our confirmation notification. "
                "Time slots are best-effort estimates, not guarantees — traffic, weather, "
                "earlier jobs overrunning and technician availability can shift them, and we "
                "will keep you informed. Someone aged 18 or over must be present at the "
                "address for the visit. Please ensure safe access to the appliance and a "
                "working power supply. If our technician cannot access the site, nobody is "
                "present, or the visit is unsafe, it counts as a customer no-show and the "
                "visit/inspection charge in §5 applies."
            ),
        },
        {
            "id": "pricing",
            "title": "5. Pricing, Estimates & Payment",
            "content": (
                "Prices shown at booking are the base charge for the selected service in "
                "your city and include applicable GST unless stated otherwise. Diagnosis "
                "sometimes reveals additional labour or spare parts: the technician will "
                "quote them on the spot and start work only after you approve the revised "
                "quotation in the app. Spare parts are charged at the quoted price. Payment "
                "is due on completion, by UPI, card or cash, unless a “pay later” "
                "arrangement has been agreed in writing. A visit/inspection charge is "
                "payable for a diagnostic visit even if you decline the repair, and for a "
                "customer no-show. We issue a GST invoice for every completed job."
            ),
        },
        {
            "id": "cancellation",
            "title": "6. Cancellation & Rescheduling",
            "content": (
                "You can cancel or reschedule free of charge until the technician is "
                "dispatched. After dispatch, or on a customer no-show, the visit charge "
                "applies. Full details, timelines and refund routes are in our Refund & "
                "Cancellation Policy, which forms part of these Terms."
            ),
        },
        {
            "id": "warranty",
            "title": "7. Service Warranty",
            "content": (
                "We warrant our workmanship for 30 days from job completion, and spare "
                "parts we supply for the period stated on the invoice (typically 3–6 months, "
                "or the manufacturer’s period for branded parts). If the same fault recurs "
                "within the warranty period, we will re-attend at no labour cost. The "
                "warranty does not cover: a different or new fault; damage from misuse, "
                "voltage fluctuation, water ingress, pests or physical impact; work or parts "
                "supplied by anyone else after our visit; consumables such as gas top-ups "
                "where a leak was declined for repair; or appliances the technician recorded "
                "as beyond economic repair. Raise a warranty claim in the app or by calling "
                "support with your invoice number."
            ),
        },
        {
            "id": "your-obligations",
            "title": "8. Your Obligations",
            "content": (
                "You agree to: give accurate information; be present or nominate an adult; "
                "keep pets restrained and the work area clear; not ask technicians to do "
                "unsafe, unrelated or unlawful work; not pay technicians outside the app "
                "except for cash amounts recorded on the invoice; and treat our staff with "
                "respect. Abuse, harassment or threats towards a technician will end the "
                "visit immediately and may terminate your account. You are responsible for "
                "backing up data on smart appliances before service."
            ),
        },
        {
            "id": "liability",
            "title": "9. Limitation of Liability",
            "content": (
                "We are liable for direct loss or damage caused by our negligence during a "
                "service visit, and we carry insurance for this. Report any damage within "
                "48 hours of the visit, with photographs, so we can investigate. To the "
                "extent permitted by law we are not liable for: indirect or consequential "
                "loss (lost income, spoiled food, data loss, alternative accommodation); "
                "pre-existing faults or wear we did not cause; failure of an appliance "
                "already beyond economic repair; or delays caused by events outside our "
                "control (strikes, weather, civic disruption, parts unavailability). Except "
                "where law provides otherwise, our total liability for any booking is capped "
                "at the amount you paid for that booking."
            ),
        },
        {
            "id": "ip",
            "title": "10. Intellectual Property",
            "content": (
                f"The {site} name, logo, apps, website, content and software are owned by "
                f"{c['legal_name']} and protected by law. You may use them only to book and "
                "manage services. You may not copy, scrape, decompile, resell or create "
                "derivative works from them, or use our branding without written permission."
            ),
        },
        {
            "id": "termination",
            "title": "11. Suspension & Termination",
            "content": (
                "You may stop using the service and request account deletion at any time "
                "(see the Privacy Policy). We may suspend or terminate access, with notice "
                "where practical, for breach of these Terms, fraud, non-payment, or abuse of "
                "staff. Amounts already due remain payable, and completed-job warranties "
                "survive termination."
            ),
        },
        {
            "id": "law",
            "title": "12. Governing Law, Disputes & Contact",
            "content": (
                "These Terms are governed by the laws of India. Please raise any dispute "
                f"with us first at {c['email']} or {c['phone']} — we aim to resolve "
                "complaints within 30 days. Unresolved disputes are subject to the "
                "exclusive jurisdiction of the courts at our registered office. We may "
                "update these Terms; material changes will be notified at least 14 days in "
                f"advance. Registered office: {c['who']}."
            ),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════
# REFUND & CANCELLATION POLICY
# ══════════════════════════════════════════════════════════════════════════
def _refund_sections(c: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "id": "overview",
            "title": "1. Overview",
            "content": (
                f"This policy explains when you can cancel a booking, what it costs, and "
                f"how {c['site_name']} issues refunds. It applies to every service booked "
                "through our website or apps and forms part of our Terms of Service. Nothing "
                "here limits your rights under the Consumer Protection Act, 2019."
            ),
        },
        {
            "id": "free-cancellation",
            "title": "2. Free Cancellation Window",
            "content": (
                "Cancel or reschedule at no charge any time before a technician is "
                "dispatched to your address — use the “Cancel booking” option in the app or "
                "call support. If you prepaid, the full amount is refunded. Rescheduling "
                "before dispatch is always free and does not count as a cancellation."
            ),
        },
        {
            "id": "late-cancellation",
            "title": "3. Late Cancellation & No-Show",
            "content": (
                "Once the technician has been dispatched, a visit/inspection charge becomes "
                "payable to cover travel and time. The same charge applies if nobody aged 18 "
                "or over is present at the address, the technician cannot access the "
                "appliance, or the site is unsafe to work in. If you prepaid, we refund the "
                "balance after deducting that charge. Please cancel as early as you can — it "
                "frees the slot for another customer."
            ),
        },
        {
            "id": "we-cancel",
            "title": "4. If We Cancel",
            "content": (
                "If we cancel a confirmed booking — no technician available, a spare part "
                "cannot be sourced, or the location turns out to be unserviceable — you pay "
                "nothing and any prepaid amount is refunded in full. We will offer the "
                "earliest alternative slot first."
            ),
        },
        {
            "id": "unsatisfactory",
            "title": "5. Unsatisfactory or Incomplete Work",
            "content": (
                "Tell us within 48 hours of the visit if the job was not completed or the "
                "fault persists. We will re-attend free of charge under the 30-day "
                "workmanship warranty. If we still cannot fix the reported fault, we refund "
                "the labour/service charge for that job. Spare parts already fitted and "
                "working are not refundable, but a defective part is replaced free within its "
                "warranty period. Where a repair is not viable, the technician records the "
                "appliance as beyond economic repair and only the inspection charge applies."
            ),
        },
        {
            "id": "parts",
            "title": "6. Spare Parts & Special Orders",
            "content": (
                "Parts you approved in a quotation and that were specially ordered for your "
                "appliance cannot be cancelled once ordered, unless they arrive defective or "
                "wrong. Returned or unused parts are refunded once they are back with us and "
                "verified. Gas charging, chemical cleaning and other consumed services are "
                "not refundable after completion."
            ),
        },
        {
            "id": "how-refunds-work",
            "title": "7. How & When Refunds Are Paid",
            "content": (
                "Refunds go back to the original payment method: UPI and card refunds are "
                "initiated within 3 business days of approval and typically reach you in 5–7 "
                "business days depending on your bank; cash payments are refunded by UPI or "
                "bank transfer to details you confirm. Coupon and wallet amounts are returned "
                "to the wallet. We email or notify you the refund reference once initiated, "
                "and issue a credit note against the original GST invoice."
            ),
        },
        {
            "id": "amc",
            "title": "8. AMC & Subscription Plans",
            "content": (
                "Annual Maintenance Contracts can be cancelled within 7 days of purchase for "
                "a full refund if no visit has been used. After that, we refund pro-rata for "
                "the unused months, less the value of visits already provided and any "
                "onboarding discount. AMC plans are not transferable to another address "
                "outside our service area."
            ),
        },
        {
            "id": "contact",
            "title": "9. Raising a Refund Request",
            "content": (
                f"Email {c['email']} or call {c['phone']} with your booking ID and invoice "
                "number. We acknowledge within 48 hours, decide within 7 business days, and "
                "explain the reason if a request is declined. Unresolved complaints can be "
                f"escalated to our Grievance Officer at {c['who']}."
            ),
        },
    ]


# ══════════════════════════════════════════════════════════════════════════
# TEMPLATE ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════
_BUILDERS = {
    "privacy":       _privacy_sections,
    "terms":         _terms_sections,
    "refund-policy": _refund_sections,
}


def build_legal_page(page_key: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Render one default legal page for a domain. Returns None for unknown keys."""
    builder = _BUILDERS.get(page_key)
    if builder is None:
        return None

    site = ctx["site_name"]
    title = LEGAL_PAGE_LABELS[page_key]

    subtitles = {
        "privacy": (
            f"What {site} collects — including location, camera and device data — "
            "why we collect it, who we share it with, and how to have it deleted."
        ),
        "terms": (
            f"The terms and conditions that govern your use of {site} and any service "
            "you book through our website or apps."
        ),
        "refund-policy": (
            f"When you can cancel, what it costs, and how {site} issues refunds and "
            "credit notes."
        ),
    }
    metas = {
        "privacy": (
            f"Privacy Policy | {site}",
            f"How {site} collects, uses, shares and protects your personal data, "
            "including precise and background location, camera images, device "
            "identifiers and payment data. Includes account deletion instructions.",
        ),
        "terms": (
            f"Terms of Service | {site}",
            f"The terms and conditions governing bookings, pricing, warranty and "
            f"liability for services provided by {site}.",
        ),
        "refund-policy": (
            f"Refund & Cancellation Policy | {site}",
            f"{site} cancellation windows, visit charges, warranty re-visits and how "
            "refunds are processed back to your original payment method.",
        ),
    }
    meta_title, meta_description = metas[page_key]

    return {
        "page_key":         page_key,
        "title":            title,
        "subtitle":         subtitles[page_key],
        "sections":         builder(ctx),
        "footer_note":      _footer_note(page_key, ctx),
        "effective_date":   ctx["updated"],
        "meta_title":       meta_title,
        "meta_description": meta_description,
        # Legal pages MUST be publicly reachable and indexable — Google Play's
        # reviewers fetch the privacy-policy URL directly.
        "robots":           "index,follow",
        "is_published":     True,
    }


def _footer_note(page_key: str, c: dict[str, Any]) -> str:
    if page_key == "privacy":
        return (
            "We take your privacy seriously. If you ever have a concern about how we "
            "handle your data — especially your location — write to us and we will "
            "answer it properly, not with a form letter."
        )
    if page_key == "terms":
        return (
            "If anything here is unclear, ask us before you book. We would rather "
            "explain a clause up front than argue about it afterwards."
        )
    return (
        "If you think a charge or refund is wrong, tell us. Most disputes turn out to "
        "be a misunderstanding we can fix the same day."
    )


def build_all_legal_pages(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Render every default legal page for a domain, in display order."""
    pages = [build_legal_page(k, ctx) for k in LEGAL_PAGE_KEYS]
    return [p for p in pages if p is not None]
