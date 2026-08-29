/* Prahari Central Bilingual Language Logic */

function initLanguage() {
    let selectedLang = localStorage.getItem('prahari_lang');
    if (!selectedLang || selectedLang === 'undefined') {
        const userLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
        if (userLang.startsWith('hi')) {
            selectedLang = 'hindi';
        } else {
            selectedLang = 'english';
        }
        localStorage.setItem('prahari_lang', selectedLang);
    }
    setLanguageTheme(selectedLang);
}

function setLanguageTheme(lang) {
    if (!lang || lang === 'undefined') lang = 'english';
    document.documentElement.setAttribute('lang', lang === 'hindi' ? 'hi' : 'en');
    localStorage.setItem('prahari_lang', lang);
    
    // Dynamically sync browser tab title based on language
    try {
        const currentTitle = document.title;
        if (lang === 'hindi') {
            if (currentTitle.includes('Civic Assistance & Emergency Response')) {
                document.title = currentTitle.replace('Civic Assistance & Emergency Response', 'तत्काल नागरिक सूचना एवं सहायता प्रणाली');
            } else if (currentTitle.includes('Report an Incident')) {
                document.title = currentTitle.replace('Report an Incident', 'घटना की रिपोर्ट करें');
            } else if (currentTitle.includes('Report Status')) {
                document.title = currentTitle.replace('Report Status', 'रिपोर्ट की स्थिति');
            } else if (currentTitle.includes('Coordinator Login')) {
                document.title = currentTitle.replace('Coordinator Login', 'समन्वयक लॉगिन');
            } else if (currentTitle.includes('Coordinator Dashboard')) {
                document.title = currentTitle.replace('Coordinator Dashboard', 'समन्वयक डैशबोर्ड');
            } else if (currentTitle.includes('Coordinator Detail')) {
                document.title = currentTitle.replace('Coordinator Detail', 'समन्वयक विवरण');
            }
        } else {
            if (currentTitle.includes('तत्काल नागरिक सूचना एवं सहायता प्रणाली')) {
                document.title = currentTitle.replace('तत्काल नागरिक सूचना एवं सहायता प्रणाली', 'Civic Assistance & Emergency Response');
            } else if (currentTitle.includes('घटना की रिपोर्ट करें')) {
                document.title = currentTitle.replace('घटना की रिपोर्ट करें', 'Report an Incident');
            } else if (currentTitle.includes('रिपोर्ट की स्थिति')) {
                document.title = currentTitle.replace('रिपोर्ट की स्थिति', 'Report Status');
            } else if (currentTitle.includes('समन्वयक लॉगिन')) {
                document.title = currentTitle.replace('समन्वयक लॉगिन', 'Coordinator Login');
            } else if (currentTitle.includes('समन्वयक डैशबोर्ड')) {
                document.title = currentTitle.replace('समन्वयक डैशबोर्ड', 'Coordinator Dashboard');
            } else if (currentTitle.includes('समन्वयक विवरण')) {
                document.title = currentTitle.replace('समन्वयक विवरण', 'Coordinator Detail');
            }
        }
    } catch(e) {
        console.error('Error updating document title:', e);
    }
    
    // Highlight active lang pill in header
    const pills = document.querySelectorAll('.lang-pill');
    pills.forEach(pill => {
        if (pill.getAttribute('data-lang') === lang) {
            pill.classList.add('active');
        } else {
            pill.classList.remove('active');
        }
    });

    // Sync select dropdown in header
    const select = document.querySelector('.lang-selector-select');
    if (select) {
        select.value = lang;
    }

    // Dispatch global language updated event for other scripts to re-render translations if needed
    window.dispatchEvent(new CustomEvent('prahariLanguageUpdated', { detail: { lang: lang } }));
}

function changeLanguage(lang) {
    setLanguageTheme(lang);
}

window.addEventListener('DOMContentLoaded', initLanguage);
