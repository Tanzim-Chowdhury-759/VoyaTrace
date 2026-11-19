"""
Seed Germany data into Supabase. Run once after applying database/schema.sql:

    python -m scripts.seed_germany

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

from core.db import get_db
from core.embeddings import embed_texts
from core.parser_ingest import chunk_text

COUNTRY = "Germany"

ROUTES = []

def R(rg, docs, rules, sub=None):
    ROUTES.append({
        "route_group": rg,
        "sub_path": sub,
        "docs": docs,
        "rules": rules,
    })


def _deactivate_rules(db, route):
    q = (db.table("visa_rules").update({"is_active": False})
         .eq("country", COUNTRY).eq("route_group", route["route_group"])
         .eq("is_active", True))
    if route["sub_path"]:
        q = q.eq("sub_path", route["sub_path"])
    else:
        q = q.is_("sub_path", "null")
    q.execute()


def _delete_required(db, route):
    q = (db.table("required_documents").delete()
         .eq("country", COUNTRY).eq("route_group", route["route_group"]))
    if route["sub_path"]:
        q = q.eq("sub_path", route["sub_path"])
    else:
        q = q.is_("sub_path", "null")
    q.execute()


# ---------- ROUTE 1 ----------
R("Skilled Worker", [
    ("passport", "Valid passport (10y, ≥2 blank pages)", True, "D", 1),
    ("photo", "Biometric photo 35x45mm, white bg", True, "D", 2),
    ("application_form", "VIDEX national visa application form", True, "D", 3),
    ("passport_copy", "A4 copy of passport data page", True, "D", 4),
    ("cv", "CV / professional résumé", True, "D", 5),
    ("employer_declaration", "Employer's Erklärung zum Beschäftigungsverhältnis", True, "D", 6),
    ("employment_contract", "Employment contract / binding job offer", True, "F", 7),
    ("degree_certificate", "Academic or vocational qualification certificate", True, "D", 8),
    ("recognition_proof", "anabin printout / ZAB Statement of Comparability", False, "C", 9),
    ("health_insurance", "Compulsory German health insurance confirmation", True, "D", 10),
    ("travel_insurance", "Incoming travel insurance for arrival gap", True, "D", 11),
], """Skilled Worker Visa (§18a / §18b AufenthG) — 2026 rules.

You need a recognised academic or vocational qualification and a concrete offer of qualified employment. The job does not generally have to match your qualification, but must be qualified employment (auxiliary/unskilled work is not sufficient). Regulated professions require the applicable licence (Berufsausübungserlaubnis).

Salary rules (2026):
- Under 45: no general statutory minimum salary is stated for §18a/§18b. Pay must satisfy applicable employment conditions.
- First-time employment at age 45+: at least €55,770 gross/year, or adequate pension provision.
- Do NOT apply the Blue Card threshold to this route.

Required documents: valid passport (issued within 10 years, at least two blank pages, no observations on data page), biometric photo (35x45mm, white background, 70–80% face), VIDEX application, Section 18 declaration + employment-visa annexure, signed employer's Erklärung zum Beschäftigungsverhältnis (replaces the work contract on the Dhaka checklist — keep the actual contract as supporting evidence), academic/vocational certificates + transcripts, recognition/comparability evidence (anabin / ZAB), professional licence if regulated, CV, German compulsory health insurance effective from start date, and separate incoming travel insurance for the gap before compulsory cover begins.

Source: German Embassy Dhaka skilled-worker page; Make it in Germany — Work Visa for Qualified Professionals. Note: the Dhaka page still displays 2024-era Blue Card figures — not applicable here.""")

# ---------- ROUTE 2 ----------
R("EU Blue Card", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo 35x45mm", True, "D", 2),
    ("application_form", "VIDEX application form", True, "D", 3),
    ("passport_copy", "A4 copy of passport data page", True, "D", 4),
    ("cv", "CV", True, "D", 5),
    ("degree_certificate", "University degree certificate(s) and transcripts", True, "D", 6),
    ("recognition_proof", "anabin / ZAB Statement of Comparability", True, "F", 7),
    ("employment_contract", "Job offer / contract (≥6 months, matches qualification)", True, "F", 8),
    ("employer_declaration", "Erklärung zum Beschäftigungsverhältnis", True, "D", 9),
    ("section_82_declaration", "Section 82 declaration (signed by applicant)", True, "D", 10),
    ("salary_evidence", "Evidence of gross annual salary + duties/qualification match", True, "D", 11),
    ("health_insurance", "Compulsory German health insurance", True, "D", 12),
    ("ba_approval", "Federal Employment Agency approval (if reduced threshold)", False, "C", 13),
], """EU Blue Card (§18g AufenthG) — 2026 rules.

Eligibility: comparable higher qualification + qualifying German job offer for at least 6 months + salary at or above the applicable threshold. The job must match the qualification.

2026 salary thresholds:
- Standard: €50,700 gross/year.
- Shortage occupation: €45,934.20 gross/year, with Federal Employment Agency approval.
- Qualifying new entrant (last degree less than 3 years ago): €45,934.20 gross/year, with BA approval.
- IT specialist without a formal degree: at least 3 years relevant IT experience in the previous 7 years, university-level, job offer ≥6 months, reduced threshold €45,934.20, with BA approval.

CRITICAL SOURCE CONFLICT: The German Embassy Dhaka page (dated 14 January 2026) still displays Blue Card figures labelled "starting from 1 January 2024" (€41,041.80 and €45,300). Do NOT use those. Use the 2026 federal figures above and flag the Dhaka page as not updated on those amounts.

Documents: passport, biometric photo, VIDEX, A4 passport copy, university degree + transcripts, anabin/ZAB comparability evidence, job offer ≥6 months matching qualification, signed employer Erklärung, Section 82 declaration, salary evidence, professional licence if regulated, CV, compulsory health insurance (plus incoming travel cover for gap), BA approval where reduced threshold is used, visa fee.""")

# ---------- ROUTE 3 ----------
R("Professionally Experienced Worker", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application form", True, "D", 3),
    ("cv", "CV", True, "D", 4),
    ("degree_certificate", "Foreign academic or vocational qualification certificate", True, "F", 5),
    ("recognition_proof", "Recognition evidence by source country + ZAB/anabin", True, "F", 6),
    ("work_references", "Employment certificates: ≥2 years relevant experience in last 5 years", True, "F", 7),
    ("employment_contract", "German job offer / contract (non-regulated, related to experience)", True, "F", 8),
    ("employer_declaration", "Erklärung zum Beschäftigungsverhältnis", True, "F", 9),
    ("salary_evidence", "Contract stating gross annual salary", True, "F", 10),
    ("health_insurance", "Health insurance", True, "D", 11),
], """Professionally Experienced Worker Visa (§19c(2) AufenthG + §6 BeschV) — 2026 rules.

Eligibility: state-recognised foreign qualification + at least 2 years relevant qualified experience within the last 5 years + a qualifying non-regulated job in Germany. The qualification is not required to be fully recognised in Germany — the route exists precisely for certain non-regulated jobs without full German recognition. Non-academic vocational qualifications generally must represent at least two years of training.

2026 salary conditions:
- Under 45: at least €45,630 gross/year (or qualifying collective-agreement pay).
- Over 45: at least €55,770 gross/year or adequate pension provision.

Documents: foreign qualification certificate, proof of recognition by the country where it was obtained, employment certificates proving ≥2 years relevant experience in the last 5 years, German job offer in a non-regulated profession related to the experience, employer Erklärung zum Beschäftigungsverhältnis, contract with gross salary stated, plus standard Dhaka identity documents, insurance, fee.""")

# ---------- ROUTE 4 (three sub-paths) ----------
for sp, extra_docs, note in [
    ("Professionally Experienced IT (no degree)",
     [("work_references", "Employment certificates: ≥2 years relevant IT experience in last 5 years", True, "F", 7)],
     "Requires ≥2 years relevant qualified IT experience in last 5 years + qualifying non-regulated job. Salary conditions of Experienced Worker route apply (2026: €45,630 under 45; €55,770 at 45+ or pension)."),
    ("IT Blue Card without degree",
     [("work_references", "Employment certificates: ≥3 years IT experience in previous 7 years", True, "F", 7),
      ("ba_approval", "Federal Employment Agency approval (reduced threshold)", True, "C", 8)],
     "Requires ≥3 years relevant IT experience in previous 7 years, university-level, job offer ≥6 months, reduced Blue Card threshold €45,934.20 (2026) with BA approval."),
    ("Degree-qualified IT worker",
     [("degree_certificate", "IT degree / vocational IT qualification", True, "C", 7)],
     "Qualify through standard Skilled Worker route or Blue Card, whichever matches qualification, job and salary conditions. See those routes for 2026 thresholds."),
]:
    R("IT Specialist", [
        ("passport", "Valid passport", True, "D", 1),
        ("photo", "Biometric photo", True, "D", 2),
        ("application_form", "Application form", True, "D", 3),
        ("cv", "Technical CV (roles, technologies, projects, dates)", True, "F", 4),
        ("employment_contract", "German IT job offer (role, duties, salary, duration)", True, "F", 5),
        ("employer_declaration", "Erklärung zum Beschäftigungsverhältnis", True, "D", 6),
    ] + extra_docs + [
        ("health_insurance", "Health insurance", True, "D", 9),
    ], f"""IT Specialist — {sp}.

Common supporting documents across all IT sub-paths: passport, biometric photo, application, A4 copy, technical CV, German IT job offer (role, duties, salary, working hours, duration), employer Erklärung zum Beschäftigungsverhältnis, employment certificates showing title/duties/skills/dates, IT degree or training certificates if held, language evidence if required, BA pre-approval if applicable.

DO NOT MIX the two experience tests:
- Professionally Experienced IT (no degree): ≥2 years relevant qualified experience in last 5 years + qualifying non-regulated job + Experienced Worker salary conditions (2026: €45,630 under 45; €55,770 at 45+ or pension).
- IT Blue Card without degree: ≥3 years relevant IT experience in previous 7 years, university-level, job offer ≥6 months, 2026 reduced Blue Card threshold €45,934.20 and BA approval.
- Degree-qualified IT worker: standard Skilled Worker or Blue Card route.

Path-specific rule: {note}""", sub=sp)

# ---------- ROUTE 5 ----------
R("Opportunity Card", [
    ("passport", "Valid passport (10y, ≥2 blank pages)", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "VIDEX application + signed declaration of consent", True, "D", 3),
    ("passport_copy", "A4 copy of passport data page", True, "D", 4),
    ("degree_certificate", "Vocational or academic qualification certificate", True, "D", 5),
    ("work_references", "Work experience confirmation letters", False, "C", 6),
    ("cv", "CV", True, "D", 7),
    ("motivation_letter", "Motivation letter (intended job, language learning, why Germany, applications)", True, "D", 8),
    ("block_account", "Blocked account €1,091/month (2026) OR Verpflichtungserklärung", True, "D", 9),
    ("health_insurance", "Health insurance (Schengen-wide ≥€30,000, or public + 3-week travel)", True, "D", 10),
    ("language_certificate", "German A1 and/or English B2 (points option only)", False, "C", 11),
], """Opportunity Card (Chancenkarte, §§20a–20b AufenthG) — 2026 rules.

Two eligibility options:
1. Fully recognised skilled worker — provide evidence of full recognition in Germany (anabin / ZAB). No points or language proof required under federal guidance (German recommended).
2. Points-based — state-recognised qualification (≥2 years training) + ZAB confirmation + at least A1 German and/or B2 English + ≥6 points.

Financial proof for 2026: blocked account of at least €1,091 per month plus return flight funds, OR an original formal Declaration of Commitment (Verpflichtungserklärung §§66, 68). A concrete part-time job contract may also count if it contains the required work and pay details. Funds and health insurance are both required — not alternatives.

Health insurance: private German incoming cover valid throughout the Schengen Area with at least €30,000 coverage, or public German provider letter + travel insurance for the first three weeks. Must be provided no later than visa collection.

Operating conditions: card normally issued for up to 1 year; permits part-time work up to 20 hours/week and trial work up to 2 weeks per employer. Flight/hotel bookings not required at application — do not book before approval. Approximate minimum processing time at Embassy Dhaka: 6 weeks.""")

# ---------- ROUTE 6 ----------
R("Post-Study Job-Seeker", [
    ("passport", "Valid passport + current German residence permit", True, "F", 1),
    ("graduation_proof", "Official German degree / completion certificate", True, "F", 2),
    ("health_insurance", "Health insurance cover", True, "F", 3),
    ("livelihood_proof", "Proof of livelihood during job search", True, "F", 4),
    ("residence_registration", "Residence registration / address", False, "C", 5),
], """Post-Study Job-Seeker Residence Permit (§20 AufenthG) — 2026 rules.

This is normally NOT a separate visa from Bangladesh. It is a residence permit applied for INSIDE Germany at the local Ausländerbehörde after completing a German qualification.

Rules: eligible third-country graduates may receive up to 18 months to find qualified employment; may work in any occupation while searching; not renewable — apply for the next suitable residence title before the current status expires.

Documents: valid passport + current German residence permit, official proof of completed German studies or vocational training, health insurance, proof of livelihood, residence registration if requested, local application form and any additional documents requested by the competent Foreigners Authority.

Do not label this as an overseas job-seeker visa. For applicants applying from abroad without a job offer, the Opportunity Card is the principal job-search route.""")

# ---------- ROUTE 7 ----------
R("Qualification Recognition", [
    ("passport", "Valid passport", True, "F", 1),
    ("application_form", "National visa application + declarations", True, "F", 2),
    ("degree_certificate", "Foreign qualification certificates + transcripts", True, "F", 3),
    ("partial_recognition_notice", "Partial-recognition notice (Defizitbescheid / Anerkennungsbescheid)", True, "F", 4),
    ("qualification_measure_enrollment", "Enrolment in qualification measure (adaptation / course / job-related German)", True, "F", 5),
    ("employer_declaration", "If on-the-job: employer development plan + salary", False, "C", 6),
    ("ba_approval", "BA approval for company-based measure", False, "F", 7),
    ("german_language_proof", "German language proof (usually ≥A2)", True, "F", 8),
    ("livelihood_proof", "Proof of livelihood for entire stay", True, "F", 9),
    ("health_insurance", "Health insurance", True, "F", 10),
], """Qualification Recognition Visa (§16d(1) AufenthG) — 2026 rules.

For applicants whose foreign professional qualification was assessed as only PARTIALLY equivalent and who need a specific measure to reach full recognition.

Central evidence — do NOT overlook: the official partial-recognition notice (Defizitbescheid / Anerkennungsbescheid) from the competent German recognition authority, identifying the missing skills, AND confirmation of registration/admission to an appropriate qualification measure. A generic "I applied for recognition" statement is not sufficient.

Livelihood proof (2026, depends on measure type):
- Company-based measure: monthly remuneration at least €1,200 gross or €941 net.
- School-based measure: at least €1,091 net/month through blocked account or Declaration of Commitment.
- Skills-analysis route: at least €1,091/month; German usually A2 or above; visa issued for up to 6 months.

Additional: German language usually ≥A2; if mainly on-the-job, employer's development plan + salary/remuneration during the measure; BA approval for company-based measures where required; professional licence / evidence of steps toward it for regulated professions.

Documents: passport, national visa application, biometric photo, qualification certificates + transcripts + experience evidence, partial-recognition notice, enrolment in qualification measure, language proof, livelihood proof, health insurance.""")

# ---------- ROUTE 8 ----------
R("Recognition Partnership", [
    ("passport", "Valid passport", True, "D", 1),
    ("degree_certificate", "State-recognised foreign qualification", True, "F", 2),
    ("employment_contract", "German job offer", True, "F", 3),
    ("employer_declaration", "Employer's partnership agreement for recognition", True, "F", 4),
    ("german_language_proof", "German A2 certificate", True, "F", 5),
    ("livelihood_proof", "Proof of livelihood", True, "F", 6),
    ("health_insurance", "Health insurance", True, "F", 7),
], """Recognition Partnership Visa — 2026 rules.

For applicants with a state-recognised foreign qualification, a job offer with a German employer, and an employer agreement to support qualification recognition while working. Requires at least A2 German.

Documents: state-recognised foreign qualification, concrete German job offer, employer agreement for recognition partnership, A2 German certificate, proof of livelihood, health insurance, passport and standard identity documents. Federal route requirements apply; confirm the Dhaka submission channel and exact local checklist before filing.""")

# ---------- ROUTE 9 ----------
R("Researcher", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Researcher §18d application", True, "D", 3),
    ("hosting_agreement", "Signed hosting agreement with German research institution", True, "F", 4),
    ("cv", "Academic CV", True, "F", 5),
    ("degree_certificate", "Relevant academic background evidence", True, "F", 6),
    ("health_insurance", "Health insurance", True, "D", 7),
], """Researcher Visa (§18d AufenthG) — 2026 rules.

For researchers with a signed hosting agreement with a recognised German research institution and relevant academic background.

Key rule: a PhD student without a hosting agreement is directed by the Embassy to apply through the Student route, not the Researcher route.

Dhaka channel: embassy appointment booking page; approximate minimum processing time 3 weeks. Stipend may qualify for fee exemption in certain cases.

Documents: passport, biometric photo, signed hosting agreement, academic CV, relevant academic credentials, health insurance, application forms per Embassy Dhaka researcher checklist.""")

# ---------- ROUTE 10 ----------
R("ICT Card", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "ICT application", True, "D", 3),
    ("group_employment_proof", "Proof of ≥6 months prior employment in group company", True, "F", 4),
    ("ict_assignment_letter", "Group-company transfer letter (>90 days)", True, "F", 5),
    ("degree_certificate", "Qualification evidence", True, "F", 6),
    ("ba_approval", "BA approval", True, "C", 7),
    ("health_insurance", "Health insurance", True, "D", 8),
], """ICT Card (Intra-Corporate Transfer) — 2026 rules.

For intra-corporate transfers: the applicant must have been employed by the group company for at least 6 months prior to transfer, and the transfer must exceed 90 days.

Dhaka channel: email the Embassy to request an appointment — the FAQ states this category is not available in the new online system. BA approval required.

Documents: proof of group-company employment ≥6 months, transfer/assignment letter, qualification evidence, BA approval, standard identity and insurance documents.""")

# ---------- ROUTE 11 ----------
R("Freelance / Self-Employment", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application form", True, "D", 3),
    ("cv", "CV", True, "D", 4),
    ("business_plan", "Business plan (freelance: clients/projects; business: financing plan)", True, "F", 5),
    ("financing_plan", "Financing plan / proof of funds", True, "F", 6),
    ("livelihood_proof", "Proof of livelihood", True, "F", 7),
    ("health_insurance", "Health insurance", True, "D", 8),
], """Freelance / Self-Employment Visa — 2026 rules.

Two distinct legal subtypes with different evidence:
- Freelance (freiberuflich): clients/projects evidence + business plan.
- Business self-employment (gewerblich): business plan + financing plan.

Do NOT treat client letters as a substitute for a business plan, or vice versa.

Livelihood proof for the entire stay required. Health insurance required. Dhaka channel: contact the Embassy — business plan, financing plan and CV must be provided BEFORE an appointment can be offered.

Documents: passport, biometric photo, application, CV, business plan and/or financing plan per subtype, livelihood proof, health insurance.""")

# ---------- ROUTE 12 ----------
R("Student Visa", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "VIDEX + signed declarations", True, "D", 3),
    ("university_admission", "Admission letter from German university", True, "D", 4),
    ("degree_certificate", "Prior academic certificates + transcripts", True, "D", 5),
    ("language_certificate", "German or English proficiency per program", True, "D", 6),
    ("block_account", "Blocked account (2026 student rate)", True, "D", 7),
    ("health_insurance", "German statutory or qualifying private health insurance", True, "D", 8),
    ("cv", "CV", True, "D", 9),
    ("motivation_letter", "Motivation / study-plan letter", True, "D", 10),
], """Student Visa (national visa for study in Germany) — 2026 rules.

For applicants admitted to a German university (degree or preparatory course) who will reside in Germany for study. Requires university admission, prior academic proof, language proficiency at the level required by the program, proof of livelihood (blocked account per current student rate), and health insurance.

Documents: passport, biometric photo, VIDEX application + signed declarations, admission letter, prior degrees/transcripts, language certificate, blocked account, health insurance, CV, motivation letter. Embassy Dhaka submission via online application / waiting-list procedure. Approximate minimum processing time: 4 weeks.""")

# ---------- ROUTE 13 ----------
R("Student Applicant Visa", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "VIDEX + signed declarations", True, "D", 3),
    ("university_correspondence", "Proof of application / admission process to German university", True, "D", 4),
    ("degree_certificate", "Prior academic certificates", True, "D", 5),
    ("language_certificate", "Language proficiency evidence", True, "D", 6),
    ("block_account", "Proof of funds for applicant period", True, "D", 7),
    ("health_insurance", "Health insurance", True, "D", 8),
], """Student Applicant Visa — 2026 rules.

For applicants who have not yet received university admission but must be in Germany to complete the application process (e.g. entrance exams, interviews, preparatory course). Requires evidence of the in-progress application, prior academic credentials, language proficiency, proof of funds, and health insurance. Usually convertible to a Student Visa after admission.""")

# ---------- ROUTE 14 ----------
R("PhD / Doctoral Study", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application + declarations", True, "D", 3),
    ("hosting_agreement", "Signed hosting/supervision agreement", True, "F", 4),
    ("degree_certificate", "Master's degree / equivalent + transcripts", True, "F", 5),
    ("cv", "Academic CV", True, "F", 6),
    ("language_certificate", "Language proficiency per program", True, "D", 7),
    ("block_account", "Proof of funds (unless salaried/stipend)", True, "D", 8),
    ("health_insurance", "Health insurance", True, "D", 9),
], """PhD / Doctoral Study Visa — 2026 rules.

Two pathways depending on the arrangement:
1. Employment-based doctorate (paid position) — treated as Researcher route or employment route.
2. Scholarship / stipend-based doctorate with a signed hosting/supervision agreement — treated as Researcher route (if hosting agreement) or Student route (per Embassy Dhaka guidance).

Rule: a PhD student WITHOUT a hosting agreement is directed by the Embassy to apply through the Student route, not the Researcher route.

Documents: passport, biometric photo, signed hosting/supervision agreement, Master's degree + transcripts, academic CV, language proficiency, proof of funds (unless salaried/stipend), health insurance.""")

# ---------- ROUTE 15 ----------
R("Ausbildung / Vocational Training", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application + declarations", True, "D", 3),
    ("training_contract", "Signed Ausbildung contract with German employer", True, "F", 4),
    ("school_certificate", "School-leaving certificate + transcripts", True, "D", 5),
    ("language_certificate", "German B1 or B2 as required", True, "D", 6),
    ("livelihood_proof", "Proof of funds / training salary", True, "D", 7),
    ("health_insurance", "Health insurance", True, "D", 8),
], """Ausbildung / Vocational Training Visa — 2026 rules.

For applicants with a signed vocational training contract with a German employer. Requires school-leaving certificate, German language proficiency (usually B1–B2 depending on the trade), and proof of livelihood (training salary or blocked account).

Documents: passport, biometric photo, application, training contract, school certificates, German language certificate, livelihood proof, health insurance.""")

# ---------- ROUTE 16 ----------
R("Training Place-Seeker", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application + declarations", True, "D", 3),
    ("school_certificate", "School-leaving certificate + transcripts", True, "D", 4),
    ("language_certificate", "German B1 or higher", True, "D", 5),
    ("block_account", "Proof of funds", True, "D", 6),
    ("health_insurance", "Health insurance", True, "D", 7),
], """Training Place-Seeker Visa — 2026 rules.

For applicants entering Germany to search for an Ausbildung (vocational training) placement. Requires at least B1 German, school certificates, and proof of funds for the search period. Convertible to Ausbildung visa once a training contract is signed.""")

# ---------- ROUTE 17 ----------
R("German Language Course", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application + declarations", True, "D", 3),
    ("language_course_enrollment", "Enrolment confirmation from German language school", True, "D", 4),
    ("block_account", "Blocked account (2026 rate)", True, "D", 5),
    ("health_insurance", "Health insurance", True, "D", 6),
], """German Language Course Visa — 2026 rules.

For applicants enrolling in an intensive German language course in Germany (usually ≥18 hours/week). Requires enrolment confirmation, proof of funds (blocked account at 2026 rate), and health insurance. Typically convertible to Student/Study Applicant visa after language completion.""")

# ---------- ROUTE 18 ----------
R("Internship", [
    ("passport", "Valid passport", True, "D", 1),
    ("photo", "Biometric photo", True, "D", 2),
    ("application_form", "Application + declarations", True, "D", 3),
    ("internship_contract", "Internship agreement with German host", True, "F", 4),
    ("degree_certificate", "Enrolment proof / degree in progress", True, "D", 5),
    ("language_certificate", "Language proficiency as required", True, "D", 6),
    ("livelihood_proof", "Proof of funds (unless internship paid)", True, "D", 7),
    ("health_insurance", "Health insurance", True, "D", 8),
], """Internship Visa — 2026 rules.

For applicants undertaking an internship with a German host (typically during or shortly after study). Requires internship agreement, proof of student status or degree relevance, language proficiency, proof of funds (unless paid) and health insurance. BA approval may apply for certain internships (not auto-checked).""")


# ---------- INGEST ----------
def main():
    db = get_db()

    for route in ROUTES:
        label = route["route_group"] + (
            f" / {route['sub_path']}" if route["sub_path"] else "")
        print(f"\n=== {label}")

        _delete_required(db, route)

        doc_rows = [{
            "country": COUNTRY,
            "route_group": route["route_group"],
            "sub_path": route["sub_path"],
            "doc_type": d[0],
            "doc_label": d[1],
            "is_required": d[2],
            "evidence_label": d[3],
            "display_order": d[4],
        } for d in route["docs"]]
        if doc_rows:
            db.table("required_documents").insert(doc_rows).execute()

        chunks = chunk_text(route["rules"])
        print(f"  {len(chunks)} chunks")
        vectors = embed_texts(chunks)

        _deactivate_rules(db, route)

        rows = [{
            "country": COUNTRY,
            "route_group": route["route_group"],
            "sub_path": route["sub_path"],
            "section_title": "Overview",
            "chunk_index": i,
            "content": c,
            "embedding": v,
            "effective_year": 2026,
            "is_active": True,
            "version": 1,
        } for i, (c, v) in enumerate(zip(chunks, vectors))]
        db.table("visa_rules").insert(rows).execute()
        time.sleep(0.3)

    print("\nDone.")


if __name__ == "__main__":
    main()