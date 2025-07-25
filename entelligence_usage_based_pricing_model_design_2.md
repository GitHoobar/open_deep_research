# Usage-Based Pricing Model Design - entelligenceAI/backend
*Generated by Entelligence Doc Agent*

---
# Usage-Based Pricing Design for Code Review & Documentation Platform  
**Date:** Wed Jul 23, 2025  
**Audience:** Engineering Team (Backend, Billing, DevOps)  
---  

## 1. Executive Summary  

Hey team,  
We’ve got to turn our existing platform into a finely tuned machine that tracks exactly how much our users are leveraging our code review and doc generation APIs — and charge them accordingly. This means tracking every bit of usage (lines reviewed, docs generated, API calls), running pricing logic that handles tiers, free trials, and overages, integrating tightly with payment providers for billing, and wrapping it all into smooth customer account workflows.

I dug through our existing codebase to see where and how we can hook in with minimal disruption but clean extensibility. I’m laying out a plan that connects usage tracking right down to core request handlers, plugs pricing rules into billing workflows, and provides admin and user tools for managing credit/quota and subscriptions. You’ll get ticket-ready chunks with file references and even code snippets.  

The goal is an end-to-end system that handles everything from metering to billing to customer lifecycle management seamlessly, secure, and scalable.

---

## 2. Current State Deep Dive  

Here’s what already exists, as per our codebase:  

- **User & Account models**: `user/models.py` — User/Account info, subscription tier stored here but no extended usage fields.  
- **API endpoints**: `api/views.py` — REST API controllers for code review (`CodeReviewViewSet`) and documentation generation (`DocGenViewSet`).  
- **Usage logging**: Minimal. `logging` module usage scattered, no persistent metering found.  
- **Billing integration**: A simple Stripe integration in `billing/stripe.py` with recurring payments but no usage-linked charges or overage support.  
- **Admin dashboard**: Basic user management in `admin/views.py`, no billing or usage data yet.  
- **Notification system**: Email notifications (`notifications/email.py`) only for generic announcements, no usage/billing alerts.  
- **Security**: API keys stored in `settings.py`, basic token auth in `auth/token_auth.py`, no PCI-focused security controls.  
- **Logging & audit**: `utils/audit.py` tracks user actions but doesn’t extend to billing or usage changes.  

---

## 3. Proposed Technical Design  

### A. Usage Tracking Mechanisms  

- **Where**: Instrument the core API endpoints (`api/views.py`) for code review and documentation generation.  
- **What**: Track per user/account:  
  - Number of API calls  
  - Lines of code reviewed (extract from request payload in `CodeReviewViewSet.process_request()`)  
  - Documentation pages generated (`DocGenViewSet.generate_docs()`)  
- **How**:  
  1. Add `UsageRecord` model in `billing/models.py` — captures type (`API_CALL`, `LINES_REVIEWED`, `DOCS_GENERATED`), quantity, timestamp, user/account FK.  
  2. Introduce `UsageTracker` helper class (`billing/usage_tracker.py`) with methods:  
     - `track_api_call(user, endpoint_type)`  
     - `track_lines_reviewed(user, line_count)`  
     - `track_docs_generated(user, doc_count)`  
  3. Each API view calls `UsageTracker` immediately after successful processing to create `UsageRecord` entries.  
- **Batch vs Real-time**: Capture usage on the fly (write-through), batch aggregation for billing happens nightly.

  

### B. Pricing Computation  

- **Tiered pricing model** stored in `billing/pricing.py` as JSON/ORM-backed config, with fields:  
  - Free tier limits (e.g., up to 1000 API calls/month free)  
  - Prices per usage unit (per API call, per 100 lines, per doc page) depending on subscription tier (Basic, Pro, Enterprise)  
  - Overage rates and discounts for enterprise  
- **Billing computation service**: `billing/pricing_engine.py`  
  - Runs once nightly via Cron (`billing/billing_job.py`)  
  - Aggregates usage per account for the period  
  - Computes charges applying tiers, free quotas, overages  
  - Generates invoice lines (linked `Invoice` model in `billing/models.py`)  
- **Support for custom Enterprise plans**: extend pricing table with plan_id FK, allow custom prices.  
- **Trials**: Managed via `Account.subscription_trial_ends` in `user/models.py` and usage flags in `billing/models.py`.

  

### C. Billing Integration  

- Extend current Stripe integration (`billing/stripe.py`):  
  - Add usage-based metered billing via Stripe Metered Billing API. Sync `UsageRecord`s in batches.  
  - Invoice generation mirrors pricing computations, including proration handled by Stripe subscriptions.  
  - Payment failures tracked in `billing/models.py` (`PaymentStatus` field on Invoice). Retry logic in `billing/payment_retry.py`.  
- Support PayPal via modular billing backend (`billing/provider_paypal.py`) for enterprise clients.  

  

### D. Customer Management  

- **Signup flow** (`user/views.py`) enhanced to:  
  - Capture payment info and assign default free tier quotas  
  - Enable trials with start/end date  
- **Upgrade/Downgrade** APIs added to `user/views.py` with new endpoints:  
  - `POST /account/change-plan` - handles proration calls to Stripe integrations  
- **Account suspension/reactivation**: Add `Account.status` enum field, toggleable in `user/views.py` and admin UI.  
- **Cancellation**: Grace period logic codified, cancellation API marks flags and processes final bill.  
- **Support team accounts** by extending `Account` with `team_members` M2M field in `user/models.py`. Usage aggregated or per-member tracked.

  

### E. Credit/Quota System  

- **Model (`billing/credit.py`)**: Track prepaid credits/usage quotas per account.  
- **API (`billing/credit_manager.py`)**: Functions to allocate, deduct, refund credits, expose management endpoints (`billing/views.py`).  
- **UI/Admin**: Admin dashboard `admin/billing.py` offers views to adjust quotas.  
- **Integration**: API endpoints and usage tracking consult quota before allowing usage (rate-limit enforcement).

  

### F. Notifications & Reporting  

- **Usage alerts**: Implement threshold watchers in `notifications/usage_alerts.py`, e.g., notify at 75%, 90% of quota usage.  
- **Billing reminders**: Extend `notifications/billing_reminder.py` to auto-send pre-due and overdue reminders.  
- **Reports**: Generate monthly/annual usage reports in PDF/CSV from `billing/reporting.py` and email via scheduled jobs.

  

### G. Admin Tools  

- Add `admin/billing_dashboard.py`:  
  - Usage visualizations by account  
  - Invoice status, payment failures, disputes management  
  - Quota adjustments  
  - Dispute workflow (flag invoice/item, audit entries)  

  

### H. Scalability & Performance  

- Store UsageRecords in partitioned DB table by month (`billing/models.py`).  
- Use optimized batch aggregation jobs with indexing on `user_id`, `timestamp`.  
- Cache recent usage in Redis (`billing/cache.py`) for quick checking (e.g., quotas).  
- Async tasks with Celery for heavy billing/report generation jobs.

  

### I. Security Considerations  

- Encrypt sensitive billing data (`billing/models.py` fields encrypted with AES).  
- Store API keys securely using vault or environment variables.  
- Access controls (`auth/permissions.py`) enforcing RBAC on billing/admin endpoints.  
- Follow PCI compliance best practices—capture only minimal card data, tokenize via Stripe.  
- Use HTTPS for all billing related requests.

  

### J. Audit Logging & Monitoring  

- Extend `utils/audit.py` to log all billing and quota changes.  
- Add monitoring alerts (e.g., via Prometheus exporters) for billing failures, usage tracking errors.  
- Dashboards for error rates (`monitoring/dashboard.py`).

  

### K. API and Integration Design  

- Expose usage query endpoints:  
  - `GET /billing/usage?period=monthly` returns usage records and current quota.  
- Plan management:  
  - `POST /billing/plan/update` to change/user subscriptions/tiers.  
- Integrate with CRM/ERP via webhooks (`billing/webhooks.py`) on billing events.

---

## 4. Implementation Tickets  

**Ticket 1: Add UsageRecord model and UsageTracker helper**  
- Files: `billing/models.py`, `billing/usage_tracker.py`  
- Tasks: Define model, implement tracker functions, add unit tests  

**Ticket 2: Instrument code review and doc gen APIs for usage tracking**  
- Files: `api/views.py` (`CodeReviewViewSet.process_request()`, `DocGenViewSet.generate_docs()`)  
- Tasks: Inject usage tracking calls post-successful processing  

**Ticket 3: Implement pricing engine and nightly billing job**  
- Files: `billing/pricing.py`, `billing/pricing_engine.py`, `billing/billing_job.py`  
- Tasks: Pricing rules, aggregation, and invoice generation logic  

**Ticket 4: Extend Stripe integration for metered billing and failure handling**  
- Files: `billing/stripe.py`, `billing/payment_retry.py`  
- Tasks: Sync usage, handle retries, store payment statuses  

**Ticket 5: Customer management APIs for subscription lifecycle**  
- Files: `user/views.py`  
- Tasks: Signup/signup with payment, plan change APIs, suspension/reactivation  

**Ticket 6: Credit/quota system implementation and admin UI**  
- Files: `billing/credit.py`, `billing/credit_manager.py`, `admin/billing.py`  
- Tasks: Models, APIs, dashboard views  

**Ticket 7: Notifications for usage alerts and billing reminders**  
- Files: `notifications/usage_alerts.py`, `notifications/billing_reminder.py`  
- Tasks: Setup triggers and email templates  

**Ticket 8: Admin billing dashboard and dispute management features**  
- Files: `admin/billing_dashboard.py`  
- Tasks: UI components for usage, invoices, disputes  

**Ticket 9: Security hardening for billing and API keys**  
- Files: `settings.py`, `auth/permissions.py`, `billing/models.py` (encryption)  
- Tasks: Encrypt fields, access control improvements  

**Ticket 10: Audit logging extension for billing actions**  
- Files: `utils/audit.py`, integration in billing functions  
- Tasks: Log all billing related data changes  

**Ticket 11: Scalability improvements (partitioning, caching, async jobs)**  
- Files: `billing/models.py` (partitioning), `billing/cache.py`, `billing/billing_job.py` (Celery)  
- Tasks: Partition tables, implement Redis caches, setup Celery task runners  

**Ticket 12: API endpoints for usage/query and plan updates**  
- Files: `billing/views.py`  
- Tasks: Usage query APIs, plan updates, webhook handlers for external system integration  

---

## 5. Code Examples  

### UsageRecord model snippet (`billing/models.py`)  

```python
class UsageRecord(models.Model):
    ACCOUNT_METRIC_CHOICES = [
        ('API_CALL', 'API Call'),
        ('LINES_REVIEWED', 'Lines Reviewed'),
        ('DOCS_GENERATED', 'Documentation Pages Generated'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    metric = models.CharField(max_length=20, choices=ACCOUNT_METRIC_CHOICES)
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
```

### UsageTracker helper (`billing/usage_tracker.py`)  

```python
from .models import UsageRecord

class UsageTracker:
    @staticmethod
    def track_api_call(user, endpoint_type):
        UsageRecord.objects.create(user=user, metric='API_CALL', quantity=1)

    @staticmethod
    def track_lines_reviewed(user, lines_count):
        UsageRecord.objects.create(user=user, metric='LINES_REVIEWED', quantity=lines_count)

    @staticmethod
    def track_docs_generated(user, docs_count):
        UsageRecord.objects.create(user=user, metric='DOCS_GENERATED', quantity=docs_count)
```

### Integrate in CodeReviewViewSet (`api/views.py`)  

```python
from billing.usage_tracker import UsageTracker

class CodeReviewViewSet(viewsets.ViewSet):
    def process_request(self, request):
        # existing logic
        reviewed_lines = count_lines(request.data['code'])
        # After successful review
        UsageTracker.track_api_call(request.user, 'code_review')
        UsageTracker.track_lines_reviewed(request.user, reviewed_lines)
        return Response(...)
```

---

## 6. Migration & Deployment  

1. Add new DB tables (`UsageRecord`, `Invoice`, `Credit`) with initial migrations.  
2. Deploy usage tracking code into API services, enable feature flags initially for sampling usage accuracy.  
3. Roll out pricing engine nightly job on staging, validate invoice correctness with test accounts.  
4. Integrate Stripe metered billing in dev/staging, simulate payment lifecycle.  
5. Launch customer management flows progressively.  
6. Enable admin dashboards and notifications after usage data stabilizes.  
7. Secure secrets and run penetration testing on billing flows.  
8. Monitor logs and metrics carefully in first weeks to tune usage aggregation and retry policies.

---

## 7. Edge Cases & Risks  

- **Delayed usage ingestion**: Ensure batch job can handle late-arriving usage records, apply them with backdated timestamps.  
- **Incorrect usage counts**: Add monitoring on usage spikes, alerts for anomalies. Validate counts during early rollout.  
- **Payment failures on large invoices**: Implement retry with escalating user notifications. Consider invoice splitting if needed.  
- **Trial abuse**: Detect excessive usage in trial and throttle or flag suspicious accounts.  
- **Quota exhaustion race conditions**: Use Redis-backed locking when decrementing quotas to avoid double spend.  
- **Security breaches**: Rotate API keys regularly, restrict billing admin routes to minimum privilege. Use WAF and logging.  

---

Any clarifications or code walk-throughs you want to pair on next? I can queue up the repo branches and PR templates once tickets are ready.

Cheers!