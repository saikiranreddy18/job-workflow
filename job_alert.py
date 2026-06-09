"""
Job Alert System for Sai Kiran Reddy
Searches multiple platforms, filters entry-level remote jobs open to India,
sends email digest to saik180821@gmail.com
"""

import requests
import smtplib
import json
import os
import hashlib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TO_EMAIL     = "sanjanatallapureddy@gmail.com"
FROM_EMAIL   = os.environ.get("saikiranreddytallapureddy@gmail.com")   # your Gmail
APP_PASSWORD = os.environ.get("ycbe caeo hchn wnpo")  # Gmail App Password
SEEN_FILE    = "seen_jobs.json"

 Your skills — used for relevance scoring
SKILLS = [
    "kafka", "spark", "databricks", "delta lake", "python", "pyspark",
    "mlflow", "kubernetes", "docker", "terraform", "aws", "airflow",
    "langchain", "llm", "rag", "prompt engineering", "ml", "ai",
    "machine learning", "data engineer", "devops", "pytorch", "xgboost",
    "n8n", "fastapi", "sql", "postgresql", "data pipeline", "etl"
]
 
# HARD FILTERS — skip if job contains these
BLOCK_PHRASES = [
    "us citizen", "must be a citizen", "security clearance",
    "authorized to work in the united states",
    "without visa sponsorship", "us work authorization",
    "require sponsorship", "only us", "uscis", "green card required",
    "must reside in the us", "united states residents only",
    "5 years", "7 years", "10 years", "senior", "lead engineer",
    "staff engineer", "principal engineer", "director"
]
 
# GOOD SIGNALS — job is open to India
GOOD_PHRASES = [
    "worldwide", "anywhere in the world", "open to all",
    "international", "global remote", "india", "work from anywhere",
    "contractor", "contract", "freelance", "no sponsorship required",
    "all countries", "remote first", "distributed team"
]
 
# ─── SEEN JOBS (avoid re-alerting) ────────────────────────────────────────────
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()
 
def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)
 
def job_id(job):
    return hashlib.md5((job.get("title","") + job.get("company","") + job.get("url","")).encode()).hexdigest()
 
# ─── RELEVANCE SCORE ──────────────────────────────────────────────────────────
def score_job(job):
    text = (job.get("title","") + " " + job.get("description","")).lower()
    # Block check
    for phrase in BLOCK_PHRASES:
        if phrase in text:
            return -1  # blocked
    # Score based on skill matches
    score = sum(2 for skill in SKILLS if skill in text)
    # Bonus for good signals
    score += sum(3 for phrase in GOOD_PHRASES if phrase in text)
    # Bonus for entry-level keywords
    entry_keywords = ["entry level", "junior", "associate", "new grad",
                      "fresh", "0-1", "0 year", "no experience", "trainee", "intern"]
    score += sum(2 for kw in entry_keywords if kw in text)
    return score
 
# ─── SOURCE 1: We Work Remotely ───────────────────────────────────────────────
def scrape_wwr():
    jobs = []
    categories = [
        "https://weworkremotely.com/remote-jobs-artificial-intelligence-ai",
        "https://weworkremotely.com/remote-jobs/search?term=data+engineer",
        "https://weworkremotely.com/remote-jobs/search?term=python+developer",
        "https://weworkremotely.com/remote-jobs/search?term=machine+learning",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in categories:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for li in soup.select("li.feature, li:has(a[href*='/remote-jobs/'])"):
                a = li.find("a", href=True)
                if not a: continue
                title_el = li.find(class_=["title","position"])
                company_el = li.find(class_=["company","region"])
                title = title_el.text.strip() if title_el else a.text.strip()
                company = company_el.text.strip() if company_el else "Unknown"
                link = "https://weworkremotely.com" + a["href"] if a["href"].startswith("/") else a["href"]
                region_el = li.find(class_="region")
                region = region_el.text.strip() if region_el else ""
                jobs.append({
                    "title": title, "company": company,
                    "url": link, "source": "WeWorkRemotely",
                    "description": title + " " + region,
                    "location": region, "pay": "Not listed"
                })
        except Exception as e:
            print(f"WWR error: {e}")
    return jobs
 
# ─── SOURCE 2: RemoteOK ───────────────────────────────────────────────────────
def fetch_remoteok():
    jobs = []
    tags = ["python", "machine-learning", "data", "devops", "ai", "kafka"]
    headers = {"User-Agent": "job-alert-bot/1.0"}
    try:
        r = requests.get("https://remoteok.com/api", headers=headers, timeout=15)
        data = r.json()
        for job in data[1:]:  # first item is metadata
            title = job.get("position", "")
            company = job.get("company", "")
            url = job.get("url", "")
            description = job.get("description", "") + " " + " ".join(job.get("tags", []))
            pay = f"${job.get('salary_min','')}-${job.get('salary_max','')}" if job.get("salary_min") else "Not listed"
            jobs.append({
                "title": title, "company": company,
                "url": url, "source": "RemoteOK",
                "description": description,
                "location": "Remote", "pay": pay
            })
    except Exception as e:
        print(f"RemoteOK error: {e}")
    return jobs
 
# ─── SOURCE 3: Wellfound (AngelList) ─────────────────────────────────────────
def scrape_wellfound():
    jobs = []
    searches = [
        "https://wellfound.com/jobs?role=data-engineer&remote=true&locationSlugs=&",
        "https://wellfound.com/jobs?role=machine-learning-engineer&remote=true",
        "https://wellfound.com/jobs?role=devops-engineer&remote=true",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in searches:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select("[class*='JobListing'], [class*='job-card'], div[data-test='StartupResult']"):
                title_el = card.find(["h2","h3","a"])
                title = title_el.text.strip() if title_el else "Data/ML Role"
                a = card.find("a", href=True)
                link = "https://wellfound.com" + a["href"] if a and a["href"].startswith("/") else (a["href"] if a else url)
                jobs.append({
                    "title": title, "company": "Startup (Wellfound)",
                    "url": link, "source": "Wellfound",
                    "description": title + " remote worldwide entry level",
                    "location": "Remote", "pay": "Equity + Salary"
                })
        except Exception as e:
            print(f"Wellfound error: {e}")
    return jobs
 
# ─── SOURCE 4: YC Job Board ───────────────────────────────────────────────────
def fetch_yc_jobs():
    jobs = []
    try:
        r = requests.get(
            "https://www.workatastartup.com/jobs?demographic=any&hasSalary=false"
            "&industry=&interestInRole=&jobType=fulltime&remote=true&role=eng&sortBy=recent",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("div.job, div[class*='JobListItem'], a[href*='/jobs/']"):
            a = card.find("a", href=True) or card
            title_el = card.find(["h2","h3","span"])
            title = title_el.text.strip() if title_el else "Software Engineer"
            link = a.get("href","")
            if link and not link.startswith("http"):
                link = "https://www.workatastartup.com" + link
            jobs.append({
                "title": title, "company": "YC Startup",
                "url": link, "source": "YC WorkAtStartup",
                "description": title + " remote python data engineer worldwide",
                "location": "Remote", "pay": "Startup salary"
            })
    except Exception as e:
        print(f"YC error: {e}")
    return jobs
 
# ─── EMAIL BUILDER ────────────────────────────────────────────────────────────
def build_email(new_jobs):
    date_str = datetime.now().strftime("%b %d, %Y %I:%M %p")
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;color:#1a1a1a;">
<div style="background:#1F4E79;padding:20px;border-radius:8px 8px 0 0;">
  <h1 style="color:white;margin:0;font-size:22px;">🎯 Job Alert — {date_str}</h1>
  <p style="color:#93c5fd;margin:6px 0 0;">{len(new_jobs)} new jobs matching your profile | Remote | Entry Level | India OK</p>
</div>
<div style="background:#f8fafc;padding:20px;border-radius:0 0 8px 8px;">
"""
    for i, job in enumerate(new_jobs, 1):
        score = job.get("score", 0)
        stars = "🟢" if score >= 10 else "🔵" if score >= 5 else "⚪"
        html += f"""
<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:11px;color:#94a3b8;">#{i} · {job['source']} · Score: {score} {stars}</span>
    <span style="font-size:11px;color:#94a3b8;">{job.get('location','Remote')}</span>
  </div>
  <h3 style="margin:8px 0 4px;color:#1F4E79;font-size:16px;">{job['title']}</h3>
  <p style="margin:0 0 8px;color:#64748b;font-size:13px;">{job['company']} · {job.get('pay','Not listed')}</p>
  <a href="{job['url']}" style="background:#1F4E79;color:white;padding:7px 16px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:bold;">Apply Now →</a>
</div>"""
 
    html += """
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:14px;margin-top:16px;">
  <strong style="color:#c2410c;">📋 Your Daily Target: Apply to 50 jobs</strong><br>
  <span style="font-size:13px;color:#9a3412;">Pick the highest-scored ones first. Reply to this email if you need a tailored CV or cover letter for any role.</span>
</div>
</div></body></html>"""
    return html
 
# ─── SEND EMAIL ───────────────────────────────────────────────────────────────
def send_email(jobs):
    if not jobs:
        print("No new jobs found this run.")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 {len(jobs)} New Job Matches for You — {datetime.now().strftime('%b %d %I:%M%p')}"
    msg["From"]    = FROM_EMAIL
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(build_email(jobs), "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(FROM_EMAIL, APP_PASSWORD)
            server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
        print(f"✅ Email sent with {len(jobs)} jobs")
    except Exception as e:
        print(f"❌ Email error: {e}")
 
# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n🔍 Running job search — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    seen = load_seen()
    all_jobs = []
 
    print("Fetching WeWorkRemotely...")
    all_jobs += scrape_wwr()
    print("Fetching RemoteOK...")
    all_jobs += fetch_remoteok()
    print("Fetching Wellfound...")
    all_jobs += scrape_wellfound()
    print("Fetching YC Jobs...")
    all_jobs += fetch_yc_jobs()
 
    print(f"Total fetched: {len(all_jobs)}")
 
    # Score and filter
    new_jobs = []
    for job in all_jobs:
        jid = job_id(job)
        if jid in seen:
            continue
        score = score_job(job)
        if score <= 0:
            continue  # blocked or irrelevant
        job["score"] = score
        seen.add(jid)
        new_jobs.append(job)
 
    # Sort by score descending, take top 50
    new_jobs.sort(key=lambda x: x["score"], reverse=True)
    new_jobs = new_jobs[:50]
 
    print(f"New matching jobs: {len(new_jobs)}")
    save_seen(seen)
    send_email(new_jobs)
 
if __name__ == "__main__":
    main()
