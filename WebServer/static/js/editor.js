/* static/js/editor.js */

document.addEventListener('DOMContentLoaded', () => {
    const fileListEl = document.getElementById('file-list');
    const searchInput = document.getElementById('file-search');
    const filenameInput = document.getElementById('filename-input');
    const editorTextarea = document.getElementById('code-editor');
    const btnSave = document.getElementById('btn-save');
    const btnDelete = document.getElementById('btn-delete');
    const btnNew = document.getElementById('btn-new-file');
    const statusEl = document.getElementById('editor-status');

    let allFiles = [];
    let currentFile = null; // Nom du fichier chargé (null si nouveau)

    // 1. Charger la liste
    async function loadFiles() {
        try {
            const res = await fetch('/api/editor/list');
            if (res.ok) {
                allFiles = await res.json();
                renderFileList();
            }
        } catch (e) { console.error(e); }
    }

    function renderFileList() {
        const filter = searchInput.value.toLowerCase();
        fileListEl.innerHTML = '';
        
        const filtered = allFiles.filter(f => f.toLowerCase().includes(filter));

        if (filtered.length === 0) {
            fileListEl.innerHTML = '<div style="padding:1rem; text-align:center; color:var(--text-muted);">Aucun fichier.</div>';
            return;
        }

        filtered.forEach(file => {
            const div = document.createElement('div');
            div.className = `file-item ${currentFile === file ? 'active' : ''}`;
            div.innerHTML = `<svg style="width:16px;height:16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg> ${escapeHtml(file)}`;
            div.onclick = () => loadFileContent(file);
            fileListEl.appendChild(div);
        });
    }

    // 2. Charger un fichier
    async function loadFileContent(filename) {
        try {
            statusEl.textContent = "Chargement...";
            const res = await fetch(`/api/editor/load?file=${encodeURIComponent(filename)}`);
            if (res.ok) {
                const data = await res.json();
                currentFile = filename;
                filenameInput.value = filename;
                editorTextarea.value = data.content;
                
                // UI Updates
                btnDelete.style.display = 'inline-block';
                renderFileList(); // Update active class
                statusEl.textContent = `Chargé : ${filename}`;
            } else {
                alert("Erreur chargement fichier");
            }
        } catch (e) { console.error(e); }
    }

    // 3. Nouveau fichier
    btnNew.onclick = () => {
        currentFile = null;
        filenameInput.value = "";
        filenameInput.placeholder = "nouveau_module.yaml";
        editorTextarea.value = "# Nouveau module AlgoHub\nid: new_module\nname: ...\n";
        filenameInput.focus();
        
        btnDelete.style.display = 'none';
        renderFileList(); // Retire la classe active
        statusEl.textContent = "Nouveau fichier (non sauvegardé)";
    };

    // 4. Sauvegarder
    btnSave.onclick = async () => {
        const newName = filenameInput.value.trim();
        const oldName = currentFile;
        const content = editorTextarea.value;

        if (!newName) {
            alert("Veuillez donner un nom au fichier.");
            return;
        }

        try {
            statusEl.textContent = "Sauvegarde en cours...";
            const res = await fetch('/api/editor/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: newName, content: content })
            });

            if (res.ok) {
                const data = await res.json();
                
                if (oldName && newName !== oldName) {
                    try {
                        const deleteRes = await fetch(`/api/editor/delete?file=${encodeURIComponent(oldName)}`, { method: 'DELETE' });
                        if (!deleteRes.ok) {
                           console.error("La suppression de l'ancien fichier a échoué.");
                        }
                    } catch (e) {
                        console.error("Erreur lors de la suppression de l'ancien fichier:", e);
                    }
                }

                statusEl.textContent = "Sauvegardé avec succès !";
                currentFile = data.filename;
                filenameInput.value = currentFile;
                btnDelete.style.display = 'inline-block';
                await loadFiles();
                
                setTimeout(() => { statusEl.textContent = "Prêt."; }, 2000);

            } else {
                let errorMsg = `Erreur HTTP ${res.status}`;
                try {
                    const errorData = await res.json();
                    errorMsg = errorData.error || JSON.stringify(errorData);
                } catch (e) {
                    // Le corps de la réponse n'était pas du JSON, on utilise le texte brut.
                    const textError = await res.text();
                    if(textError) errorMsg = textError;
                }
                alert("Erreur: " + errorMsg);
                statusEl.textContent = "Erreur sauvegarde.";
            }
        } catch (e) {
            console.error("Erreur réseau inattendue:", e);
            alert("Erreur réseau: " + e.message);
        }
    };

    // 5. Supprimer
    btnDelete.onclick = async () => {
        if (!currentFile) return;
        if (!confirm(`Supprimer définitivement ${currentFile} ?`)) return;

        try {
            const res = await fetch(`/api/editor/delete?file=${encodeURIComponent(currentFile)}`, { method: 'DELETE' });
            if (res.ok) {
                btnNew.click(); // Reset UI
                loadFiles();
                statusEl.textContent = "Fichier supprimé.";
            } else {
                alert("Erreur suppression");
            }
        } catch (e) { alert("Erreur réseau"); }
    };

    // Recherche
    searchInput.addEventListener('input', renderFileList);

    // Tabulation dans le textarea (pour coder confortablement)
    editorTextarea.addEventListener('keydown', function(e) {
        if (e.key == 'Tab') {
            e.preventDefault();
            var start = this.selectionStart;
            var end = this.selectionEnd;
            this.value = this.value.substring(0, start) + "  " + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 2;
        }
    });

    // Initialisation
    loadFiles();
});