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

