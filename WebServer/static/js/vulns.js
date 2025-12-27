/* static/js/vulns.js */
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('search-input');
    const select = document.getElementById('severity-select');

    // 1. DÉFINITION : On définit la fonction AVANT de l'utiliser
    window.performSearch = async function() {
        const q = input ? input.value : '';
        const sev = select ? select.value : 'All';
        const tbody = document.getElementById('vulns-table-body');
        
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Chargement...</td></tr>';
        
        try {
            const res = await fetch(`/api/vulns/search?q=${encodeURIComponent(q)}&severity=${sev}`);
            const data = await res.json();
            
            tbody.innerHTML = '';
            
            if(data.length === 0) { 
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 2rem; color: var(--text-muted);">Aucune vulnérabilité trouvée.</td></tr>'; 
                return; 
            }
            
            data.forEach(v => {
                const tr = document.createElement('tr');
                tr.className = 'vuln-row';
                let badge = 'badge-info';
                
                // Correspondance des couleurs avec votre CSS style.css
                if(v.severity === 'CRITIQUE') badge = 'badge-danger';
                if(v.severity === 'ELEVÉ') badge = 'badge-warning'; // Orange
                if(v.severity === 'MOYEN') badge = 'badge-warning'; // Jaune
                
                tr.innerHTML = `
                    <td style="font-weight:bold; color:var(--accent-color);">${escapeHtml(v.ip)}</td>
                    <td><span class="badge ${badge}">${v.severity}</span></td>
                    <td>
                        <div style="font-weight: 600;">${escapeHtml(v.title)}</div>
                        <button class="show-details-btn" onclick="toggleDetails(${v.id})">Voir détails</button>
                        <div id="details-${v.id}" class="details-box">${escapeHtml(v.details)}</div>
                    </td>
                    <td style="color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(v.module)}</td>
                    <td style="color: var(--text-muted); font-size: 0.8rem;">${v.date}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch(e) { 
            console.error(e);
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--danger); text-align:center;">Erreur lors du chargement.</td></tr>'; 
        }
    };
    
    // Helper pour afficher/masquer les détails
    window.toggleDetails = function(id) {
        const el = document.getElementById(`details-${id}`);
        if (el) el.style.display = el.style.display === 'block' ? 'none' : 'block';
    };

    window.downloadCSV = function() {
        const query = document.getElementById('search-input').value;
        const severity = document.getElementById('severity-select').value;
        const url = `/api/vulns/export/csv?q=${encodeURIComponent(query)}&severity=${encodeURIComponent(severity)}`;
        window.location.href = url;
    };

    function escapeHtml(text) {
        if (text === null || text === undefined) {
            return "";
        }
        var map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.toString().replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    // 2. EXÉCUTION : Maintenant on peut l'utiliser sans erreur
    if(input) {
        input.addEventListener('keypress', (e) => { 
            if(e.key === 'Enter') performSearch(); 
        });
        
        // Recherche automatique au chargement de la page
        performSearch();
    }
});