const THEME_STORAGE_KEY = "theme";
const THEME_MEDIA_QUERY = "(prefers-color-scheme: light)";

function getSystemTheme() {
    return window.matchMedia && window.matchMedia(THEME_MEDIA_QUERY).matches ? "light" : "dark";
}

function getStoredTheme() {
    try {
        const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
        return storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
    } catch (error) {
        return null;
    }
}

function persistTheme(theme) {
    try {
        window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (error) {
        // Ignore storage issues and keep the in-memory selection only.
    }
}

function applyTheme(theme) {
    const nextTheme = theme === "light" ? "light" : "dark";
    const root = document.documentElement;
    root.dataset.theme = nextTheme;

    document.querySelectorAll("[data-theme-option]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.themeOption === nextTheme));
    });

    return nextTheme;
}

function initializeThemeSwitch() {
    const initialTheme = getStoredTheme() || document.documentElement.dataset.theme || getSystemTheme();
    applyTheme(initialTheme);

    document.querySelectorAll("[data-theme-option]").forEach((button) => {
        button.addEventListener("click", () => {
            const selectedTheme = applyTheme(button.dataset.themeOption);
            persistTheme(selectedTheme);
        });
    });

    if (!window.matchMedia) return;

    const mediaQuery = window.matchMedia(THEME_MEDIA_QUERY);
    const handleSystemThemeChange = () => {
        if (!getStoredTheme()) {
            applyTheme(getSystemTheme());
        }
    };

    if (typeof mediaQuery.addEventListener === "function") {
        mediaQuery.addEventListener("change", handleSystemThemeChange);
    } else if (typeof mediaQuery.addListener === "function") {
        mediaQuery.addListener(handleSystemThemeChange);
    }
}

function setupDragDrop(dropId, inputId, textId) {
    const drop = document.getElementById(dropId);
    const input = document.getElementById(inputId);
    const textSpan = document.getElementById(textId);
    if(!drop || !input || !textSpan) return;

    drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('hover'); });
    drop.addEventListener('dragleave', e => { e.preventDefault(); drop.classList.remove('hover'); });
    drop.addEventListener('drop', e => {
        e.preventDefault();
        drop.classList.remove('hover');
        if(e.dataTransfer.files.length) {
            const file = e.dataTransfer.files[0];
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            textSpan.textContent = file.name;
        }
    });

    input.addEventListener('change', () => {
        if(input.files.length) textSpan.textContent = input.files[0].name;
    });
}

function toggleOptional() {
    const fields = document.getElementById('optionalFields');
    if(!fields) return;
    fields.classList.toggle('expanded');
}

document.addEventListener("DOMContentLoaded", initializeThemeSwitch);
