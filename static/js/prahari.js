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
