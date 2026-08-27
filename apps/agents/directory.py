import logging

logger = logging.getLogger(__name__)

# Master directory database (currently empty, ready for future expansion)
# Key format: (authority_name, jurisdiction)
VERIFIED_DIRECTORY = {
    # Example structure:
    # ("National Ambulance", "National"): {
    #     "authority": "National Ambulance",
    #     "jurisdiction": "National",
    #     "contact": "108",
    #     "source": "Official Gov Helpline",
    #     "verified": True,
    #     "last_verified": "2026-08-28"
    # }
}

def get_verified_contact(authority_name: str, jurisdiction: str = "National") -> dict:
    """
    Query the verified directory for an authority contact.
    Returns the record dict if found and verified, else returns a dict with 'Verified contact unavailable'.
    """
    if not authority_name:
        return _unavailable_record("Unknown Authority", jurisdiction)

    key = (authority_name.strip(), jurisdiction.strip())
    record = VERIFIED_DIRECTORY.get(key)
    if record and record.get("verified", False):
        return record
    
    return _unavailable_record(authority_name, jurisdiction)


def _unavailable_record(authority_name: str, jurisdiction: str) -> dict:
    return {
        "authority": authority_name,
        "jurisdiction": jurisdiction,
        "contact": "Verified contact unavailable",
        "source": "None",
        "verified": False,
        "last_verified": None
    }


def sanitize_contact_number(number: str) -> str:
    """
    Deterministic safety check to filter out fake/placeholder numbers.
    Any unverified phone number is converted to 'Verified contact unavailable'.
    """
    if not number:
        return "Verified contact unavailable"
    
    num_clean = number.strip().lower()
    
    # Common placeholders to catch immediately
    placeholders = [
        "01234", "56789", "home-sec", "how to reach",
        "contact number", "placeholder", "unavailable"
    ]
    for p in placeholders:
        if p in num_clean:
            return "Verified contact unavailable"
            
    # Known official national emergency lines are allowed
    known_emergency = {"108", "100", "101", "102", "1091", "112"}
    if num_clean in known_emergency:
        return num_clean
        
    # Since they are not verified in our master database/structure,
    # return the explicit unavailable string to prevent fake phone numbers.
    return "Verified contact unavailable"
