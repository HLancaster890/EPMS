# EPMS Enterprise — Cost Estimate

## 1. Development Cost

### Phase 1: Security Hardening (Week 1-2)

| Task | Hours | Seniority | Cost |
|------|-------|-----------|------|
| Add org_id filters to 8 dashboard endpoints | 16 | Senior | $2,400 |
| Add auth to analytics live endpoint | 4 | Senior | $600 |
| Fix CORS middleware | 2 | Senior | $300 |
| Add constant-time comparisons | 2 | Senior | $300 |
| Move WS API key to first message | 8 | Senior | $1,200 |
| Fix API key hashing consistency | 4 | Senior | $600 |
| Set non-empty defaults for JWT_SECRET/INTERNAL_API_KEY | 2 | Senior | $300 |
| **Subtotal** | **38** | | **$5,700** |

### Phase 2: Bug Fixes (Week 2-3)

| Task | Hours | Seniority | Cost |
|------|-------|-----------|------|
| Remove duplicate report generation task | 1 | Mid | $100 |
| Remove duplicate startup handler | 1 | Mid | $100 |
| Fix dedup cache (TTLCache) | 3 | Senior | $450 |
| Replace dangerous f-string pattern | 2 | Senior | $300 |
| Add html.escape to report generation | 2 | Mid | $200 |
| Add timeouts (SMTP, WS, DB) | 6 | Senior | $900 |
| Add locks to shared state in analytics | 4 | Senior | $600 |
| **Subtotal** | **19** | | **$2,650** |

### Phase 3: Performance & Schema (Week 3-4)

| Task | Hours | Seniority | Cost |
|------|-------|-----------|------|
| Add missing DB indexes | 4 | Senior DBA | $800 |
| Add data retention purge function | 3 | Senior DBA | $600 |
| Batch agent scoring with ANY($1) | 4 | Senior | $600 |
| Prune stale live state entries | 2 | Senior | $300 |
| Add query timeouts to DB pools | 2 | Senior | $300 |
| Add correlation ID middleware | 3 | Senior | $450 |
| **Subtotal** | **18** | | **$3,050** |

### Phase 4: Deploy Pipeline (Week 4-5)

| Task | Hours | Seniority | Cost |
|------|-------|-----------|------|
| Fix WiX MajorUpgrade schedule | 2 | Senior DevOps | $400 |
| Fix Services.wxs duplicate components | 3 | Senior DevOps | $600 |
| Set Secure="yes" on password MSI properties | 1 | Senior DevOps | $200 |
| Wire rollback custom actions | 3 | Senior DevOps | $600 |
| Set workers=1 in config template | 1 | Mid | $100 |
| Disable UPX, add authenticode sign step | 4 | Senior DevOps | $800 |
| Add pre-install port check | 2 | Mid | $200 |
| **Subtotal** | **16** | | **$2,900** |

### Phase 5: Testing & Docs (Week 5-6)

| Task | Hours | Seniority | Cost |
|------|-------|-----------|------|
| Agent unit tests (monitors, systray, config, __main__) | 24 | Senior | $3,600 |
| Integration tests for multi-tenant isolation | 12 | Senior | $1,800 |
| Pre-deployment validation script | 6 | Mid | $600 |
| Runbook for incident response | 8 | Senior DevOps | $1,200 |
| **Subtotal** | **50** | | **$7,200** |

### Total Development Cost

| Phase | Hours | Cost |
|-------|-------|------|
| Phase 1: Security | 38 | $5,700 |
| Phase 2: Bug Fixes | 19 | $2,650 |
| Phase 3: Performance | 18 | $3,050 |
| Phase 4: Deploy Pipeline | 16 | $2,900 |
| Phase 5: Testing & Docs | 50 | $7,200 |
| **Total** | **141** | **$21,500** |

**Rate assumptions**: Senior ($150/hr), Mid ($100/hr). Based on US contractor rates. Adjust for geography.

## 2. Operational Cost

### On-Premise (Single Server)

| Item | Specification | One-Time | Monthly |
|------|--------------|----------|---------|
| Server hardware | Dell R450, Xeon 16C, 64GB, 1TB SSD | $4,500 | — |
| Windows Server 2022 Std (16-core) | ~$1,200 | $1,200 | — |
| Cal (10 users) | ~$300 | $300 | — |
| Power & cooling | 200W × 24h × 30d × $0.12/kWh | — | ~$17 |
| Internet (static IP, 100Mbps) | Business grade | — | ~$80 |
| Backup storage | External HDD or NAS | $200 | — |
| **Subtotal** | | **$6,200** | **~$97/mo** |

### Cloud (If on-prem not required)

| Provider | Spec | Monthly |
|----------|------|---------|
| Hetzner AX102 | 16C/64GB/2x1TB NVMe | ~$80 |
| DigitalOcean Droplet | 16vCPU/64GB/640GB SSD | ~$384 |
| AWS EC2 (c6i.4xlarge) | 16vCPU/32GB/EBS gp3 1TB | ~$650 + storage |
| Azure (D8s v5) | 8vCPU/32GB/EBS 1TB | ~$550 + storage |

### Managed Add-Ons (Cloud Only)

| Service | Monthly |
|---------|---------|
| Managed PostgreSQL (RDS, 100GB) | ~$200 |
| Managed Redis (ElastiCache, 5GB) | ~$50 |
| Managed NATS (Synadia) | ~$100 |
| Backup storage (S3 500GB) | ~$12 |
| Monitoring (CloudWatch, 10GB logs) | ~$30 |
| **Cloud total** | **~$400-900/mo** |

## 3. Total Cost of Ownership (3-Year Projection)

### On-Prem (Standard)

| Year | Hardware | License | Power/Net | Ops Labor | **Total** |
|------|----------|---------|-----------|-----------|-----------|
| 0 | $4,500 | $1,500 | — | $21,500 (dev) | **$27,500** |
| 1 | — | — | $1,164 | $5,000 (maintenance) | **$6,164** |
| 2 | — | — | $1,164 | $5,000 | **$6,164** |
| 3 | $1,500 (disk upgrade) | — | $1,164 | $7,000 (major upgrade) | **$9,664** |
| **3-year TCO** | **$6,000** | **$1,500** | **$3,492** | **$38,500** | **$49,492** |

### Cloud (Medium — Hetzner)

| Year | Compute | Managed Services | Ops Labor | **Total** |
|------|---------|-----------------|-----------|-----------|
| 0 | — | — | $21,500 (dev) | **$21,500** |
| 1 | $960 | $1,200 | $5,000 | **$7,160** |
| 2 | $960 | $1,200 | $5,000 | **$7,160** |
| 3 | $960 | $1,200 | $7,000 | **$9,160** |
| **3-year TCO** | **$2,880** | **$3,600** | **$38,500** | **$45,000** |

## 4. Per-Customer Pricing Guidance

Based on TCO + margin:

| Bundle | Agents | One-Time License | Annual Maintenance (20%) |
|--------|--------|-----------------|------------------------|
| Starter | <50 | $1,500 | $300 |
| Business | 50-500 | $5,000 | $1,000 |
| Enterprise | 500-5,000 | $15,000 | $3,000 |
| Unlimited | 5,000+ | $30,000 | $6,000 |

**Break-even at 3 customers** (Starter) or **2 customers** (Business).
