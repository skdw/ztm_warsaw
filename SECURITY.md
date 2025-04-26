# Security Policy  
*Warsaw Public Transport (`ztm_warsaw`) — custom integration for Home Assistant*

---

## 1. Supported Versions

I actively maintain **only the latest major branch (1.x)**.  
Older branches receive *no* patches, even for severe issues.

| Version | Status | Notes                      |
|---------|--------|----------------------------|
| `1.x`   | ✅ **Supported** | Bug & security fixes |
| `< 1.0` | ❌ **End-of-Life** | Please upgrade      |

If you discover a vulnerability while running an EOL version, upgrade first and confirm it also exists in the current release before filing a report.

---

## 2. How to Report a Vulnerability

I welcome **co-ordinated disclosure** (a private report followed by a public fix).

| Preferred method       | Where / How                                                                                                   |
|------------------------|----------------------------------------------------------------------------------------------------------------|
| **GitHub Security Advisories** | 1. Go to this repo’s **“Security”** tab. <br>2. Click **“Report a vulnerability”**. <br>3. Fill in the private form. |

> **Why private first?**  
> Public issues trigger bots, forks and mirrors—giving attackers time to weaponise the bug before users can patch.

### 2.1 Information Checklist (what helps me help you)

* **Environment** — Home Assistant version + `ztm_warsaw` version (`manifest.json` shows the number)  
* **Steps to reproduce** — as concise as possible  
* **Impact** — what an attacker could gain (e.g. *“execute arbitrary code”* / *“denial of service”*)  
* **PoC / logs / screenshots** — if available  
* **Patch idea** — optional but appreciated  

> **Tip for newcomers**  
> Unsure whether something is a security problem or just a bug? **Report it anyway**—I’ll triage. You will never be penalised for a false positive.

---

## 3. What Happens Next

| Phase                | Typical timeline                  |
|----------------------|-----------------------------------|
| **Acknowledgement**  | I reply within **72 hours**       |
| **Initial analysis** | Verify and plan a fix   |
| **Status updates**   | At least **every 7 days**         |
| **Fix released**     | ≤ **30 days** for critical issues |
| **Public disclosure**| After a patch is available (or earlier by mutual agreement) |

If I cannot meet the timeline (e.g. complex root cause), I’ll explain why and propose a new date.

---

## 4. Disclosure & Credit

* A security-only release is published and the advisory noted in the **Changelog**.  
* Reporters are **credited** by GitHub username (or “Anonymous”) unless you opt out.  
* No exploit details are revealed until a fixed version is on PyPI / HACS.

---

## 5. Hall of Fame ❤️

I thank all researchers and users who privately disclosed vulnerabilities and helped make this project safer.

---

## 6. Data-Source Disclaimer 📢

**I am *not* the provider of the timetable data.**  
This integration merely **reads** publicly available information from the City of Warsaw API (`api.um.warszawa.pl`).

* If you believe the **API itself** exposes sensitive data or behaves insecurely, please contact **Urząd Miasta Stołecznego Warszawy**.  
* Issues regarding **how the integration uses that data** (parsing, storage, display) should be reported to me as described in Section 2.

---

*Last updated: 2025-04-26* | Maintainer: **@solarssk**
