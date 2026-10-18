# Security Policy  
*Warsaw Public Transport (`ztm_warsaw`) — custom integration for Home Assistant*

---

## 1. Supported Versions

I actively maintain **only the latest release**.  
Older versions receive *no* patches, even for severe issues.

| Version                                  | Status             | Notes                                                                    |
|------------------------------------------|--------------------|--------------------------------------------------------------------------|
| The latest release (the one HACS offers) | ✅ **Supported**   | See the [Releases](https://github.com/solarssk/ztm_warsaw/releases) page |
| Anything older                           | ❌ **End-of-Life** | Please upgrade                                                           |

If you discover a vulnerability while running an EOL version, upgrade first and confirm it also exists in the latest release before filing a report.

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
* No exploit details are revealed until a fixed version is published as a GitHub Release, which is what HACS offers to users.

---

## 5. API Keys and Other Secrets

This integration needs a personal API key from the City of Warsaw. Home Assistant stores it in the integration's configuration entry on your own system, and the integration sends it to the city's API.

* **Never paste your API key into an issue, a discussion or a log excerpt.** Remove it first (the bug form asks you to confirm that you did). If a key did leak, treat it as burned: generate a new one on the city's open-data portal and stop using the old one.
* **No credential belongs in this repository or its history**: not a real key, token or password in code, tests, fixtures, logs or workflow files. Tests use clearly synthetic keys. The optional test against the real API reads its key from an environment variable, never prints it, and is not run in CI.
* If you find a credential in this repository's history, report it privately as described in Section 2 and do not use it.

---

## 6. Security Controls / CI

Automated checks that actually run in this repository. The table is kept honest rather than complete: a control is added the day it runs and removed the day it stops.

| Control | Scope | When | Where |
|---|---|---|---|
| GitHub secret scanning and push protection | Known secret formats in pushed commits | Every push | Repository setting (enabled) |
| gitleaks | Secret scan of the commits of the change | Every pull request and push to `main` | `.github/workflows/ci.yml`, job *Secret scan (gitleaks)* |
| CodeQL | Static analysis of the Python code and the workflow files | Every pull request and weekly | GitHub default setup (the repository's security settings, CodeQL analysis), no workflow file |
| pip-audit | Known vulnerabilities in the four pinned test and lint tools (not in Home Assistant's own dependencies; the integration itself has no third-party runtime requirements) | Every pull request and push to `main` | `.github/workflows/ci.yml`, job *Dependency audit (pip-audit)* |
| actionlint and zizmor | Correctness and safety of the workflow files: template injection, unpinned actions, excessive permissions | Every pull request and push to `main` | `.github/workflows/ci.yml`, job *Lint workflows (actionlint, zizmor)* |
| Dependabot | Updates of GitHub Actions (weekly) and Python tooling (monthly), with a 7-day cooldown; security updates | Scheduled | `.github/dependabot.yml` and a repository setting |
| Branch protection | A pull request and the required status checks (listed in [CONTRIBUTING.md](CONTRIBUTING.md#opening-a-pull-request)) before a change is merged to `main`; not enforced for the repository administrator | Every merge | Repository setting |
| OpenSSF Scorecard | Independent score of the repository's security practices, report only | Push to `main`, weekly | `.github/workflows/scorecard.yml` |
| SonarCloud | Code quality and security hotspots, report only | Every pull request that can read secrets (not forks or Dependabot) and every push to `main` | `.github/workflows/ci.yml`, job *Coverage signals (Codecov, SonarCloud)* |

---

## 7. Hall of Fame ❤️

I thank all researchers and users who privately disclosed vulnerabilities and helped make this project safer.

---

## 8. Data-Source Disclaimer 📢

**I am *not* the provider of the timetable data.**  
This integration merely **reads** publicly available information from the City of Warsaw open-data APIs: `api.um.warszawa.pl` for an old-style key (a UUID) and `dane.um.warszawa.pl` for a token. A key is sent only to the host that accepts it.

* If you believe the **API itself** exposes sensitive data or behaves insecurely, please contact **Urząd Miasta Stołecznego Warszawy**.  
* Issues regarding **how the integration uses that data** (parsing, storage, display) should be reported to me as described in Section 2.

---

*Last updated: 2026-10-17* | Maintainer: **@solarssk**
