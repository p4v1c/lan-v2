/* static/js/note.js */

document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('note-textarea');
    const preview = document.getElementById('note-preview');
    const statusLabel = document.getElementById('note-status');
    
    const btnEdit = document.getElementById('btn-mode-edit');
    const btnView = document.getElementById('btn-mode-view');

    let saveTimeout;

    // 1. Initialisation : Charger la note
    if(textarea) {
        fetch('/api/note')
            .then(r => r.json())
            .then(d => {
                textarea.value = d.content || '';
                // Si on charge en mode view, on update la preview direct (optionnel)
            })
            .catch(e => console.error("Erreur chargement note", e));
        
        // 2. Autosave sur frappe
        textarea.addEventListener('input', () => {
            clearTimeout(saveTimeout);
            statusLabel.style.opacity = '0'; // Cache "Sauvegardé" pendant la frappe
            
            saveTimeout = setTimeout(async () => {
                try {
                    await fetch('/api/note', {
                        method: 'POST', 
                        headers: {'Content-Type': 'application/json'}, 
                        body: JSON.stringify({content: textarea.value})
                    });
                    
                    statusLabel.textContent = "Sauvegardé";
                    statusLabel.className = "badge badge-success";
                    statusLabel.style.opacity = '1';
                    
                    // Disparait après 2s
                    setTimeout(() => { statusLabel.style.opacity = '0'; }, 2000);
                } catch(e) {
                    statusLabel.textContent = "Erreur !";
                    statusLabel.className = "badge badge-danger";
                    statusLabel.style.opacity = '1';
                }
            }, 1000); // Délai 1s
        });
    }

    // 3. Gestion Bascule Edit / View
    if (btnEdit && btnView && textarea && preview) {
        
        btnEdit.addEventListener('click', () => {
            // Activer Edit
            btnEdit.classList.add('active');
            btnView.classList.remove('active');
            
            // Afficher Textarea / Cacher Preview
            textarea.style.display = 'block';
            preview.style.display = 'none';
            
            // Focus
            textarea.focus();
        });

        btnView.addEventListener('click', () => {
            // Activer View
            btnView.classList.add('active');
            btnEdit.classList.remove('active');
            
            // Générer le Markdown
            // (marked est chargé globalement via le CDN dans note.html)
            if (typeof marked !== 'undefined') {
                preview.innerHTML = marked.parse(textarea.value);
            } else {
                preview.innerHTML = "<i>Erreur : Librairie Markdown non chargée.</i><br>" + escapeHtml(textarea.value);
            }

            // Cacher Textarea / Afficher Preview
            textarea.style.display = 'none';
            preview.style.display = 'block';
        });
    }
    
    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
});