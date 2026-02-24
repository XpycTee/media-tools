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