"""
RAG document ingestion module.
Ingests Indian legal provisions into a ChromaDB vector store.
"""

import logging
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


def ingest_legal_documents():
    """
    Ingest the 10 core Indian legal provisions into local ChromaDB collection.
    Prints confirmation for each document ingested.
    """
    # 1. Initialize local persistent client
    client = chromadb.PersistentClient(path="rag/chroma_db")
    
    # 2. Use local sentence-transformers model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # 3. Create or get collection
    collection = client.get_or_create_collection(
        name="legal_provisions",
        embedding_function=emb_fn
    )

    # 4. Core Indian legal provisions
    documents = [
        {
            "id": "const_art22",
            "document": (
                "Article 22 of the Constitution of India — Protection against arrest and detention in certain cases. "
                "No person who is arrested shall be detained in custody without being informed, as soon as may be, "
                "of the grounds for such arrest nor shall he be denied the right to consult, and to be defended by, "
                "a legal practitioner of his choice. Every person who is arrested and detained in custody shall be "
                "produced before the nearest magistrate within a period of twenty-four hours of such arrest "
                "excluding the time necessary for the journey from the place of arrest to the court of the magistrate "
                "and no such person shall be detained in custody beyond the said period without the authority of a magistrate."
            ),
            "metadata": {
                "category": "constitutional_rights",
                "act": "Constitution of India",
                "section": "Article 22"
            }
        },
        {
            "id": "crpc_sec41",
            "document": (
                "Section 41 of the Code of Criminal Procedure (CrPC) — When police may arrest without warrant. "
                "Any police officer may without an order from a Magistrate and without a warrant, arrest any person "
                "who commits, in the presence of a police officer, a cognizable offence, or against whom a reasonable complaint "
                "has been made, or credible information has been received, or a reasonable suspicion exists, that he has "
                "committed a cognizable offence punishable with imprisonment for a term which may be less than seven years or "
                "which may extend to seven years whether with or without fine, if the conditions specified in this section "
                "are satisfied. These conditions include preventing such person from committing any further offence, proper "
                "investigation of the offence, preventing tampering with evidence, or ensuring the presence of the person in court."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Code of Criminal Procedure",
                "section": "Section 41"
            }
        },
        {
            "id": "crpc_sec50",
            "document": (
                "Section 50 of the Code of Criminal Procedure (CrPC) — Person arrested to be informed of grounds of arrest "
                "and of right to bail. Every police officer or other person arresting any person without warrant shall forthwith "
                "communicate to him full particulars of the offence for which he is arrested or other grounds for such arrest. "
                "Where a police officer arrests without warrant any person other than a person accused of a non-bailable offence, "
                "he shall inform the person arrested that he is entitled to be released on bail and that he may arrange for sureties on his behalf."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Code of Criminal Procedure",
                "section": "Section 50"
            }
        },
        {
            "id": "crpc_sec57",
            "document": (
                "Section 57 of the Code of Criminal Procedure (CrPC) — Person arrested not to be detained more than twenty-four hours. "
                "No police officer shall detain in custody a person arrested without warrant for a longer period than under all "
                "the circumstances of the case is reasonable, and such period shall not, in the absence of a special order "
                "of a Magistrate under section 167, exceed twenty-four hours exclusive of the time necessary for the journey "
                "from the place of arrest to the Magistrate's court."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Code of Criminal Procedure",
                "section": "Section 57"
            }
        },
        {
            "id": "crpc_sec76",
            "document": (
                "Section 76 of the Code of Criminal Procedure (CrPC) — Person arrested to be brought before Court without delay. "
                "The police officer or other person executing a warrant of arrest shall (subject to the provisions of section 71 as to security) "
                "without unnecessary delay bring the person arrested before the Court before which he is required by law to produce such person. "
                "Provided that such delay shall not, in any case, exceed twenty-four hours exclusive of the time necessary for the journey "
                "from the place of arrest to the Magistrate's court."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Code of Criminal Procedure",
                "section": "Section 76"
            }
        },
        {
            "id": "dk_basu_guidelines",
            "document": (
                "D.K. Basu Guidelines (Supreme Court Ruling) — Mandatory procedures to be followed by police during arrest and detention. "
                "The Supreme Court of India in D.K. Basu v. State of West Bengal laid down mandatory safeguards: "
                "1. The police personnel carrying out the arrest and handling the interrogation should bear accurate, visible and clear identification "
                "and name tags with their designations. 2. A memo of arrest must be prepared at the time of arrest, witnessed by at least one witness "
                "(either a family member or respected citizen of the locality), and countersigned by the arrestee. 3. The arrestee is entitled to have "
                "a family member, relative, or friend informed of the arrest and the place of detention as soon as possible (within 8 to 12 hours). "
                "4. The arrestee must be medically examined at the time of arrest and re-examined every 48 hours of detention. 5. Copies of all documents "
                "must be sent to the Area Magistrate."
            ),
            "metadata": {
                "category": "judicial_guidelines",
                "act": "Supreme Court Ruling",
                "section": "D.K. Basu Guidelines"
            }
        },
        {
            "id": "const_art21",
            "document": (
                "Article 21 of the Constitution of India — Protection of life and personal liberty. "
                "No person shall be deprived of his life or personal liberty except according to procedure established by law. "
                "This guarantees the right to live with human dignity, right to a fair trial, right to speedy justice, "
                "and protection against police brutality and torture in custody."
            ),
            "metadata": {
                "category": "constitutional_rights",
                "act": "Constitution of India",
                "section": "Article 21"
            }
        },
        {
            "id": "parmanand_katara_ruling",
            "document": (
                "Right to Emergency Medical Treatment (Supreme Court Ruling in Parmanand Katara v. Union of India) — "
                "The Supreme Court ruled that preservation of human life is of paramount importance. "
                "Every injured citizen brought for medical treatment should instantaneously be given medical aid to preserve life, "
                "and thereafter the procedural criminal law should be allowed to operate. "
                "Government and private hospitals and doctors cannot deny or delay emergency medical treatment to a victim under the pretext of waiting "
                "for police clearance or registration of a medico-legal case (MLC)."
            ),
            "metadata": {
                "category": "medical_rights",
                "act": "Supreme Court Ruling",
                "section": "Parmanand Katara v. Union of India"
            }
        },
        {
            "id": "crpc_sec357",
            "document": (
                "Section 357 of the Code of Criminal Procedure (CrPC) — Order to pay compensation. "
                "When a Court imposes a sentence of fine or a sentence of which fine forms a part, the Court may, when passing judgment, "
                "order the whole or any part of the fine recovered to be applied in the payment to any person of compensation for any loss "
                "or injury caused by the offence, when compensation is, in the opinion of the Court, recoverable by such person in a Civil Court. "
                "This section is crucial for victim rehabilitation and compensation for rights violations."
            ),
            "metadata": {
                "category": "victim_compensation",
                "act": "Code of Criminal Procedure",
                "section": "Section 357"
            }
        },
        {
            "id": "legal_services_act",
            "document": (
                "Legal Services Authorities Act 1987 — Right to free legal aid. "
                "Section 12 of the Legal Services Authorities Act prescribes the criteria for providing free legal services to eligible persons, "
                "including women, children, members of Scheduled Castes (SC) or Scheduled Tribes (ST), industrial workmen, persons in custody (including police custody), "
                "or individuals whose annual income is below the specified threshold. The District Legal Services Authority (DLSA) and State Legal Services "
                "Authority (SLSA) are mandated to provide free legal aid, assign panel advocates, and bear all expenses of the legal proceedings."
            ),
            "metadata": {
                "category": "legal_aid",
                "act": "Legal Services Authorities Act",
                "section": "Section 12"
            }
        },
        {
            "id": "bnss_sec60",
            "document": (
                "Section 60 of the Bharatiya Nagarik Suraksha Sanhita (BNSS) — Person arrested not to be detained more than twenty-four hours. "
                "This provision replaces Section 57 of the old Code of Criminal Procedure (CrPC). It mandates that no police officer shall "
                "detain in custody a person arrested without warrant for a longer period than under all the circumstances of the case is reasonable, "
                "and such period shall not, in the absence of a special order of a Magistrate under Section 187 BNSS (formerly Section 167 CrPC), "
                "exceed twenty-four hours exclusive of the time necessary for the journey from the place of arrest to the Magistrate's court. "
                "Detaining an individual beyond 24 hours without a Magistrate's authorization is an illegal detention and a direct violation of constitutional rights."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Bharatiya Nagarik Suraksha Sanhita",
                "section": "Section 60"
            }
        },
        {
            "id": "bnss_sec35",
            "document": (
                "Section 35 of the Bharatiya Nagarik Suraksha Sanhita (BNSS) — When police may arrest without warrant. "
                "This provision replaces Section 41 of the old Code of Criminal Procedure (CrPC). It outlines the strict conditions under which "
                "a police officer may arrest a person without a warrant, particularly for offenses punishable with imprisonment for a term less "
                "than seven years. It requires the police officer to satisfy themselves that the arrest is necessary to prevent the person from "
                "committing further offenses, for proper investigation, to prevent tampering with evidence, or to prevent threatening witnesses. "
                "It also introduces safeguards like prior approval from an officer not below the rank of Deputy Superintendent of Police for arrests of individuals "
                "who are infirm or aged."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Bharatiya Nagarik Suraksha Sanhita",
                "section": "Section 35"
            }
        },
        {
            "id": "bnss_sec58",
            "document": (
                "Section 58 of the Bharatiya Nagarik Suraksha Sanhita (BNSS) — Person arrested to be informed of grounds of arrest and right to bail. "
                "This provision replaces Section 50 of the old Code of Criminal Procedure (CrPC). It mandates that every police officer or other person "
                "arresting any person without a warrant must immediately communicate to him full particulars of the offense for which he is arrested "
                "or other grounds for such arrest. Additionally, if the offense is bailable, the officer must inform the arrested person of their right "
                "to be released on bail so they may arrange for sureties on their behalf."
            ),
            "metadata": {
                "category": "arrest_procedure",
                "act": "Bharatiya Nagarik Suraksha Sanhita",
                "section": "Section 58"
            }
        },
        {
            "id": "bns_sec74",
            "document": (
                "Section 74 of the Bharatiya Nyaya Sanhita (BNS) — Punishment for voluntarily causing hurt. "
                "This provision replaces Section 323 of the old Indian Penal Code (IPC). It states that whoever voluntarily causes hurt "
                "to any person shall be punished with imprisonment for a term which may extend to one year, or with fine which may extend "
                "to ten thousand rupees, or with both. Voluntarily causing hurt is a cognizable or non-cognizable offense depending on severity, "
                "and under BNS, the penalty structure has been modernized."
            ),
            "metadata": {
                "category": "assault_provisions",
                "act": "Bharatiya Nyaya Sanhita",
                "section": "Section 74"
            }
        },
        {
            "id": "consumer_protection_act_2019",
            "document": (
                "Consumer Protection Act 2019 — Key provisions for consumer disputes, e-commerce fraud, and service deficiencies. "
                "The Consumer Protection Act 2019 provides a robust mechanism to protect the rights of consumers. It defines a 'consumer' "
                "and establishes Central Consumer Protection Authority (CCPA) to regulate matters relating to violation of consumer rights, "
                "unfair trade practices, and false or misleading advertisements. It provides for a three-tier consumer dispute redressal machinery: "
                "District Commission (for claims up to 1 crore), State Commission (up to 10 crores), and National Commission (above 10 crores). "
                "Service deficiency includes any fault, imperfection, shortcoming or inadequacy in the quality, nature and manner of performance "
                "required by law or contract."
            ),
            "metadata": {
                "category": "consumer_disputes",
                "act": "Consumer Protection Act 2019",
                "section": "Key Provisions"
            }
        },
        {
            "id": "minimum_wages_and_code_on_wages",
            "document": (
                "Minimum Wages Act 1948 and Code on Wages 2019 — Wage theft, inspector powers, and penalties. "
                "Under the Minimum Wages Act 1948 and the Code on Wages 2019, failure of an employer to pay wages on time or paying less than "
                "the prescribed minimum wages constitutes a serious statutory violation, commonly termed wage theft. The Code on Wages 2019 consolidates "
                "laws relating to wages, bonus, and gender equality. It mandates timely payment of wages (weekly, fortnightly, or monthly) "
                "and empowers Inspectors-cum-Facilitators to inspect workplaces, examine records, and prosecute errant employers. "
                "Employers who default on payment or pay below minimum wages face steep fines and penalties, and workers can claim up to ten times "
                "the difference under recovery procedures before designated authorities."
            ),
            "metadata": {
                "category": "labour_rights",
                "act": "Code on Wages 2019",
                "section": "Wage Theft Provisions"
            }
        },
        {
            "id": "tpa_sec106",
            "document": (
                "Section 106 of the Transfer of Property Act 1882 — Tenancy termination and illegal lockout provisions. "
                "Section 106 regulates the duration of certain leases in the absence of written contracts. A lease of immovable property for "
                "agricultural or manufacturing purposes is deemed to be from year to year, terminable by six months' notice, while a lease for "
                "other purposes is deemed to be from month to month, terminable by fifteen days' notice. An illegal lockout—where a landlord "
                "forcibly locks a tenant out of the premises without following due process of law—is a civil wrong and a violation of the tenant's "
                "right to peaceful possession. Tenants can seek immediate restoration of possession and damages under civil remedies."
            ),
            "metadata": {
                "category": "property_tenancy",
                "act": "Transfer of Property Act 1882",
                "section": "Section 106"
            }
        },
        {
            "id": "specific_relief_act_1963",
            "document": (
                "Specific Relief Act 1963 — Injunction against illegal eviction and recovery of possession. "
                "Under Section 6 of the Specific Relief Act 1963, if any person is dispossessed without their consent of immovable property "
                "otherwise than in due course of law, they or any person claiming through them may, by suit, recover possession thereof. "
                "This suit must be filed within six months from the date of dispossession. Additionally, tenants or occupants facing threats "
                "of illegal eviction can seek a temporary or permanent injunction under Section 37 and 38 of the Specific Relief Act to restrain the "
                "landlord from forcibly evicting them without following the legal due process."
            ),
            "metadata": {
                "category": "property_tenancy",
                "act": "Specific Relief Act 1963",
                "section": "Section 6"
            }
        },
        {
            "id": "illegal_eviction_remedies",
            "document": (
                "Illegal Eviction Remedies India. For illegal eviction by a landlord: "
                "1. Section 6 Specific Relief Act 1963 — suit for recovery of possession must be filed in Civil Court within 6 months of dispossession. "
                "2. Section 38 Specific Relief Act 1963 — suit for permanent injunction to prevent eviction, filed in Civil Court. "
                "3. BNS Section 329 (replaces IPC 441) — criminal trespass if landlord physically enters and locks out tenant — complaint to police or Magistrate. "
                "4. BNS Section 351 (replaces IPC 503) — criminal intimidation if landlord threatens tenant — complaint to police. "
                "5. Section 106 Transfer of Property Act 1882 — requires landlord to give 15 days notice for monthly tenancy, 6 months for yearly tenancy before termination. Violation = wrongful termination. Remedy: civil suit for damages. This is NOT a criminal provision."
            ),
            "metadata": {
                "category": "civil_remedy",
                "act": "SRA_TPA_BNS",
                "section": "Illegal Eviction Remedies"
            }
        },
        {
            "id": "wage_theft_remedies",
            "document": (
                "Wage Theft Remedies India. For non-payment of wages: "
                "1. Code on Wages 2019 Section 45 — file written complaint with Inspector-cum-Facilitator (not a court, not police — a labour inspector). "
                "2. Payment of Wages Act 1936 — claim before Authority under Payment of Wages Act (Labour Court). NOT a Magistrate Court complaint. "
                "3. BNS Section 111 (replaces IPC 420 cheating) — only if employer fraudulently induced workers under false promise of payment. "
                "4. Industrial Disputes Act 1947 — if 10+ workers affected, can raise industrial dispute before Labour Commissioner."
            ),
            "metadata": {
                "category": "labour_law",
                "act": "Code_on_Wages",
                "section": "Wage Theft Remedies"
            }
        }
    ]

    # 5. Ingest/upsert documents
    for doc in documents:
        collection.upsert(
            ids=[doc["id"]],
            documents=[doc["document"]],
            metadatas=[doc["metadata"]]
        )
        print(f"Ingested: {doc['id']} - {doc['metadata']['section']}")

    logger.info("Successfully ingested %d legal provisions into ChromaDB.", len(documents))


def ingest_medical_protocols():
    """
    Ingest the 8 core medical protocols into local ChromaDB collection "medical_protocols".
    Prints confirmation for each document ingested.
    """
    # 1. Initialize local persistent client
    client = chromadb.PersistentClient(path="rag/chroma_db")
    
    # 2. Use local sentence-transformers model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # 3. Create or get collection
    collection = client.get_or_create_collection(
        name="medical_protocols",
        embedding_function=emb_fn
    )

    # 4. Core medical protocols
    documents = [
        {
            "id": "triage_start_protocol",
            "document": (
                "START (Simple Triage and Rapid Treatment) Protocol. "
                "START is a triage method used by emergency responders to quickly classify victims during a mass casualty incident. "
                "Assessment is based on three main physiological parameters (RPM): "
                "1. Respiration: Assess breathing. If absent, open airway. If still absent, classify as Deceased (Black). "
                "If breathing is >30 breaths/min, classify as Immediate (Red). If breathing is <30 breaths/min, proceed to Perfusion. "
                "2. Perfusion: Assess radial pulse. If radial pulse is absent or capillary refill is >2 seconds, classify as Immediate (Red). "
                "If radial pulse is present or capillary refill is <2 seconds, proceed to Mental Status. "
                "3. Mental Status: Assess ability to follow simple commands. If unable to follow simple commands (unconscious or altered mental status), "
                "classify as Immediate (Red). If able to follow simple commands, classify as Delayed (Yellow) or Minor (Green) depending on injuries. "
                "Triage Category Summary: "
                "- Immediate (Red): Critical life-threatening injuries requiring instant intervention. "
                "- Delayed (Yellow): Serious but non-life-threatening injuries; transport can be delayed. "
                "- Minor (Green): Walking wounded; minor injuries. "
                "- Deceased (Black): Dead or unsalvageable injuries."
            ),
            "metadata": {
                "category": "medical_triage",
                "act": "START Protocol",
                "section": "Triage START"
            }
        },
        {
            "id": "mci_protocol",
            "document": (
                "Mass Casualty Incident (MCI) Protocol. "
                "An MCI is an event that overwhelms local healthcare resources due to the number and severity of casualties. "
                "Activation Criteria: Activated when the number of patients exceeds the normal capacity of the emergency department or local ambulance services. "
                "Resource Mobilization: Immediately mobilize reserve ambulances, call in off-duty medical staff, establish triage sectors, and prepare extra emergency bays. "
                "Command Structure: Establish an Incident Command System (ICS) with a designated Incident Commander, Triage Officer, Treatment Officer, and Transport Officer. "
                "Patient Distribution: Patients must be distributed across multiple regional facilities to prevent overloading a single hospital, prioritizing trauma centers for Immediate (Red) patients."
            ),
            "metadata": {
                "category": "disaster_management",
                "act": "MCI Protocol",
                "section": "Mass Casualty Incident"
            }
        },
        {
            "id": "sepsis_protocol",
            "document": (
                "Sepsis Early Warning Signs and Treatment Protocol. "
                "Sepsis is a life-threatening organ dysfunction caused by a dysregulated host response to infection. "
                "SIRS (Systemic Inflammatory Response Syndrome) Criteria: Defined by 2 or more of: temperature >38C or <36C, heart rate >90 bpm, "
                "respiratory rate >20 breaths/min, white blood cell count >12,000 or <4,000. "
                "qSOFA (Quick Sequential Organ Failure Assessment) Score: Points assigned for: 1. Respiratory rate >=22 breaths/min. "
                "2. Altered mentation. 3. Systolic blood pressure <=100 mmHg. A score >=2 indicates high risk of poor outcomes. "
                "Golden Hour Window: Time-sensitive intervention is critical within the first hour of recognition. "
                "Immediate Actions: Obtain blood cultures before administering antibiotics, administer broad-spectrum IV antibiotics, measure lactate levels, "
                "and initiate rapid fluid resuscitation (30 mL/kg of crystalloid) for hypotension."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "Sepsis Guidelines",
                "section": "Sepsis Early Warning"
            }
        },
        {
            "id": "stroke_protocol",
            "document": (
                "Stroke Recognition and Treatment Protocol. "
                "A stroke is a medical emergency requiring rapid intervention to minimize brain tissue loss. "
                "FAST Assessment: "
                "- Face: Ask the person to smile. Check if one side of the face droops. "
                "- Arm: Ask the person to raise both arms. Check if one arm drifts downward. "
                "- Speech: Ask the person to repeat a simple phrase. Check if speech is slurred or strange. "
                "- Time: If any of these signs are present, call emergency services immediately. "
                "Thrombolytic Therapy Window: Intravenous tissue plasminogen activator (tPA) or thrombolytic therapy must be administered within a strict 4.5-hour window from the onset of symptoms. "
                "Hospital Requirements: Requires a hospital with an active CT scanner, neuroimaging capabilities, and a specialized stroke care or neurology team."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "Stroke Protocol",
                "section": "FAST Stroke Recognition"
            }
        },
        {
            "id": "trauma_golden_hour",
            "document": (
                "Trauma Golden Hour Protocol. "
                "The 'Golden Hour' is the critical first 60 minutes following severe traumatic injury, during which rapid medical assessment and surgical intervention can prevent death. "
                "Primary Survey (ABCDE): "
                "- A (Airway): Assess and establish airway with cervical spine protection. "
                "- B (Breathing): Assess ventilation and oxygenation; look for chest injuries. "
                "- C (Circulation): Assess perfusion, control external hemorrhage, and establish IV access. "
                "- D (Disability): Assess neurological status using GCS and pupil response. "
                "- E (Exposure): Fully expose patient to inspect for injuries while preventing hypothermia. "
                "Hemorrhage Control: Immediate direct pressure, tourniquets, or pelvic binders to stop bleeding. "
                "Hospital Trauma Readiness: Requires immediate activation of the trauma surgical team, operating room readiness, and blood bank availability."
            ),
            "metadata": {
                "category": "trauma_care",
                "act": "Trauma Protocol",
                "section": "Trauma Golden Hour"
            }
        },
        {
            "id": "hospital_denial_treatment",
            "document": (
                "Hospital Denial of Treatment Protocol. "
                "Under Indian law and medical regulations, emergency and life-saving medical treatment cannot be withheld or denied by any hospital for any reason whatsoever. "
                "Inability to Pay: Treatment cannot be denied due to inability to pay or lack of financial deposit upfront. "
                "Lack of Documents: Denial of treatment due to lack of identity proof, Aadhaar card, or registration forms is illegal. "
                "Medico-Legal Cases (MLC) and Police Clearance: Hospitals must not delay treatment to wait for police clearance or registration of an MLC. "
                "Supreme Court Ruling: The landmark judgment in Parmanand Katara v. Union of India mandates that preservation of human life is paramount. "
                "Every doctor and hospital (government or private) has an absolute obligation to provide immediate medical aid. "
                "Steps if Denied: Document the denial, escalate to the Chief Medical Officer (CMO), request immediate transfer details, and contact the District Legal Services Authority (DLSA) for intervention."
            ),
            "metadata": {
                "category": "medical_rights",
                "act": "Supreme Court Ruling",
                "section": "Hospital Denial of Treatment"
            }
        },
        {
            "id": "mental_health_protocol",
            "document": (
                "Mental Health Crisis Protocol. "
                "This protocol applies to individuals experiencing acute psychiatric distress, self-harm ideation, or behavioral dysregulation. "
                "Suicide Risk Assessment: Evaluate intent, plan, access to means, and history of self-harm. "
                "De-escalation Techniques: Use non-threatening body language, a calm voice, clear boundaries, and active listening. Avoid confrontation or restraint unless safety is immediately threatened. "
                "Emergency Services Involvement: Contact specialized mental health crisis lines or psychiatric emergency responders. Involve law enforcement only if there is an active, violent threat to life. "
                "Involuntary Admission Rights: Under the Mental Healthcare Act 2017, involuntary admission must strictly adhere to legal guidelines, ensuring the patient's dignity, right to information, and access to a nominated representative and legal aid."
            ),
            "metadata": {
                "category": "psychiatric_care",
                "act": "Mental Healthcare Act",
                "section": "Mental Health Crisis"
            }
        },
        {
            "id": "obstetric_emergency",
            "document": (
                "Obstetric Emergency Protocol. "
                "Obstetric emergencies are life-threatening conditions occurring during pregnancy, labor, or postpartum. "
                "Eclampsia: Characterized by tonic-clonic seizures in a pregnant woman. Immediate actions: secure airway, administer Magnesium Sulfate (MgSO4) loading dose, "
                "control severe hypertension with labetalol or hydralazine, and plan emergency delivery. "
                "Postpartum Hemorrhage (PPH): Defined as blood loss >=500 mL after vaginal delivery or >=1000 mL after cesarean. "
                "Immediate actions: uterine massage, administer uterotonics (oxytocin, misoprostol, carboprost), establish dual large-bore IV access, and initiate fluid/blood replacement. "
                "Obstructed Labor: Mechanical failure of labor progression. Immediate action: monitor fetal heart rate, prepare for emergency cesarean section, and prevent uterine rupture. "
                "Surgical Escalation: Requires immediate transfer to a facility equipped with an operating theater, anesthesiologist, and blood transfusion services."
            ),
            "metadata": {
                "category": "obstetric_care",
                "act": "Obstetric Protocol",
                "section": "Obstetric Emergency"
            }
        },
        {
            "id": "stemi_protocol",
            "document": (
                "STEMI (ST-Elevation Myocardial Infarction / Heart Attack) Protocol. "
                "STEMI is a life-threatening medical emergency requiring immediate coronary reperfusion. "
                "Door-to-Balloon Time: Strict golden window of 90 minutes for primary percutaneous coronary intervention (PCI). "
                "Immediate Pharmacological Actions: Administer Aspirin 325mg orally (to be chewed immediately) to prevent further platelet aggregation. "
                "Diagnostics: Obtain a 12-lead ECG within 10 minutes of patient arrival. "
                "Alternative Therapy: If PCI is not available within 120 minutes, initiate thrombolytic therapy (thrombolysis) immediately unless contraindicated."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "STEMI Protocol",
                "section": "STEMI Heart Attack"
            }
        },
        {
            "id": "eclampsia_protocol_detailed",
            "document": (
                "Eclampsia and Severe Pre-eclampsia Medical Protocol. "
                "Eclampsia is the onset of tonic-clonic seizures in a patient with pre-eclampsia, representing a severe obstetric emergency. "
                "Golden Window: Seizure control and stabilization must occur within 30 minutes to prevent maternal and fetal hypoxia or death. "
                "Seizure Management: Administer Magnesium Sulfate (MgSO4) loading dose of 4g IV slowly over 5 minutes, followed by maintenance infusion. "
                "Hypertension Control: Administer antihypertensives (such as IV Labetalol or Hydralazine) to control blood pressure. "
                "Definitive Treatment: Arrange for emergency Cesarean section or induction of labor once the patient is stabilized."
            ),
            "metadata": {
                "category": "obstetric_care",
                "act": "Eclampsia Protocol",
                "section": "Eclampsia Protocol"
            }
        },
        {
            "id": "spinal_injury_protocol",
            "document": (
                "Spinal Injury and Cervical Spine Protection Protocol. "
                "Suspected spinal trauma requires strict immobilization to prevent secondary, permanent neurological damage. "
                "Immobilization Rules: Do NOT move the patient without proper spinal precautions. Apply a hard cervical collar immediately. "
                "Movement Technique: Use the 'log roll' technique only, requiring at least three trained responders to keep the spine in neutral alignment. "
                "Consequence of Deviation: Improper movement or lifting can cause permanent spinal cord transection and irreversible paralysis."
            ),
            "metadata": {
                "category": "trauma_care",
                "act": "Spinal Injury Protocol",
                "section": "Spinal Injury"
            }
        },
        {
            "id": "drowning_protocol",
            "document": (
                "Drowning resuscitation and emergency management protocol. "
                "Drowning requires immediate, aggressive rescue breathing and cardiovascular resuscitation. "
                "Resuscitation Priority: Initiate immediate CPR (starting with 5 rescue breaths, then 30 compressions) as soon as the victim is removed from water. "
                "Ambulance Wait: Do NOT wait for an ambulance or medical team before starting resuscitation. "
                "Thermoregulation: Remove wet clothing and initiate passive or active rewarming to prevent severe hypothermia."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "Drowning Protocol",
                "section": "Drowning"
            }
        },
        {
            "id": "burns_protocol",
            "document": (
                "Burns Assessment and Treatment Protocol. "
                "Thermal burns require rapid cooling and sterile coverage. "
                "First-line Action: Apply cool, gently running water over the burn area for a minimum of 20 minutes immediately. "
                "Prohibited Agents: Do NOT apply ice, butter, toothpaste, oil, or home remedies, as they trap heat and worsen tissue destruction. "
                "Triage and Severity: Estimate the total burn surface area (TBSA) using the Rule of Nines. Refer burns >10% TBSA or burns involving face, hands, or perineum to a specialized burn center."
            ),
            "metadata": {
                "category": "trauma_care",
                "act": "Burns Protocol",
                "section": "Burns"
            }
        },
        {
            "id": "pediatric_emergency",
            "document": (
                "Pediatric Emergency Resuscitation and Vital Ranges. "
                "Pediatric patients have distinct physiological and anatomical characteristics. "
                "Resuscitation Dosing: Always use weight-based or age-based length-tapes (e.g. Broselow tape) for drug dosages and equipment sizing. "
                "Airway Management: Pediatric airways are narrower and more anterior; avoid hyperextension of the neck. "
                "Vital Signs Monitoring: Be alert to age-specific heart and respiratory rates. Children compensate for shock longer than adults, but deteriorate rapidly once compensation fails."
            ),
            "metadata": {
                "category": "pediatric_care",
                "act": "Pediatric Protocol",
                "section": "Pediatric Emergency"
            }
        },
        {
            "id": "diabetic_emergency",
            "document": (
                "Diabetic Emergency and Glycemic Crisis Protocol. "
                "Manages acute hypoglycemia and diabetic ketoacidosis (DKA) or hyperosmolar hyperglycemic state (HHS). "
                "Differentiation: Hypoglycemia presents with rapid onset, sweating, confusion, and tremors. DKA/HHS presents with gradual onset, dehydration, and rapid deep breathing. "
                "Unconscious Patient Management: If a diabetic patient is unconscious and blood glucose cannot be checked immediately, administer immediate intravenous dextrose (or oral glucose gel if airway is secure) as a life-saving measure; hypoglycemia causes permanent brain damage within minutes."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "Diabetic Emergency Guidelines",
                "section": "Diabetic Emergency"
            }
        },
        {
            "id": "snake_bite_protocol",
            "document": (
                "Snake Bite Triage and Anti-Venom Administration Protocol. "
                "Suspected venomous snake bites require absolute immobilization and rapid hospital transfer. "
                "Limb Stabilization: Keep the affected limb completely immobilized and at or below heart level to slow venom spread. "
                "Prohibited Actions: Do NOT cut the wound, do NOT attempt to suck venom out (either by mouth or suction device), and do NOT apply a tight arterial tourniquet. "
                "Anti-Venom Window: Reach a designated hospital equipped with polyvalent anti-snake venom (ASV) within a strict golden window of 2 hours."
            ),
            "metadata": {
                "category": "emergency_medicine",
                "act": "Snake Bite Protocol",
                "section": "Snake Bite"
            }
        }
    ]

    # 5. Ingest/upsert documents
    for doc in documents:
        collection.upsert(
            ids=[doc["id"]],
            documents=[doc["document"]],
            metadatas=[doc["metadata"]]
        )
        print(f"Ingested: {doc['id']} - {doc['metadata']['section']}")

    logger.info("Successfully ingested %d medical protocols into ChromaDB.", len(documents))


def ingest_incident_to_history(incident_id: str, situation_brief: str,
                               domain: str, severity: str, resolved: bool):
    """
    Ingest a processed incident into the 'incident_history' collection.
    Embeds the situation_brief and stores metadata:
    - incident_id
    - domain
    - severity
    - resolved (bool)
    - created_at
    """
    from datetime import datetime, timezone
    import chromadb
    from chromadb.utils import embedding_functions

    logger.info("[ingest_incident_to_history] Ingesting incident_id=%s to incident_history", incident_id)
    try:
        # 1. Initialize persistent client
        client = chromadb.PersistentClient(path="rag/chroma_db")
        
        # 2. Use local sentence-transformers model
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # 3. Create or get collection
        collection = client.get_or_create_collection(
            name="incident_history",
            embedding_function=emb_fn
        )
        
        # 4. Ingest/upsert the incident
        metadata = {
            "incident_id": str(incident_id),
            "domain": str(domain),
            "severity": str(severity),
            "resolved": bool(resolved),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        collection.upsert(
            ids=[str(incident_id)],
            documents=[situation_brief],
            metadatas=[metadata]
        )
        logger.info("[ingest_incident_to_history] Successfully ingested incident_id=%s", incident_id)
    except Exception as e:
        logger.exception("Error ingesting incident %s to history: %s", incident_id, e)

