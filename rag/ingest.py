"""
RAG document ingestion module.
Ingests Indian legal provisions into a ChromaDB vector store.
"""

import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


def ingest_legal_documents():
    """
    Ingest Indian legal provisions programmatically from the centralized legal reference database.
    """
    from apps.agents.legal_reference import VERIFIED_LEGAL_DATABASE
    
    # 1. Initialize local persistent client
    client = chromadb.PersistentClient(
        path="rag/chroma_db",
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 2. Use local sentence-transformers model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # 3. Delete old collection if exists to avoid stale records, then create/get
    try:
        client.delete_collection("legal_provisions")
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name="legal_provisions",
        embedding_function=emb_fn
    )

    # 4. Map centralized database to Chroma documents format
    documents = []
    for (code, sec), record in VERIFIED_LEGAL_DATABASE.items():
        doc_id = f"{code.lower()}_{sec.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        doc_text = f"{code} Section {sec} — {record['title']}. Statutory Text: {record['statutory_text']}"
        metadata = {
            "code": code,
            "section": sec,
            "title": record["title"],
            "category": record["type"],
            "legacy_code": record.get("legacy_code") or "None",
            "legacy_section": record.get("legacy_section") or "None",
            "verified": "True"
        }
        documents.append({
            "id": doc_id,
            "document": doc_text,
            "metadata": metadata
        })

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
    client = chromadb.PersistentClient(
        path="rag/chroma_db",
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 2. Use local sentence-transformers model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # 3. Delete old collection if exists to avoid stale records, then create/get
    try:
        client.delete_collection("medical_protocols")
    except Exception:
        pass
    collection = collection = client.get_or_create_collection(
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
        client = chromadb.PersistentClient(
            path="rag/chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
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

