/* static/js/logs.js */
document.addEventListener('DOMContentLoaded', () => {
    const logsTableBody = document.getElementById('logs-table-body');
    const logsSearchInput = document.getElementById('logs-search');
    const logsSortBtn = document.getElementById('logs-sort-btn');
    
    // Elements Modale
    const logModal = document.getElementById('log-output-modal');
    const logModalTitle = document.getElementById('modal-cmd-title');
    const logModalOutput = document.getElementById('modal-cmd-output');
    const closeLogModalBtn = document.getElementById('close-log-modal');

    let allLogs = [];
    let sortDesc = true;

    if (logsTableBody) fetchLogs();

    async function fetchLogs() {
        try {
            const res = await fetch('/api/logs_history');
            if (res.ok) {
                allLogs = await res.json();
                if (allLogs.error) {
                    logsTableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--danger);">❌ DB Erreur.</td></tr>';
                    return;
                }
                renderLogs();
            }
        } catch (e) { console.error(e); }
    }

    function renderLogs() {
        const filter = logsSearchInput ? logsSearchInput.value.toLowerCase() : "";
        let filtered = allLogs.filter(l => 
            (l.command && l.command.toLowerCase().includes(filter)) || 
            (l.timestamp && l.timestamp.toLowerCase().includes(filter))
        );

        filtered.sort((a, b) => {
            const da = new Date(a.timestamp);
            const db = new Date(b.timestamp);
            return sortDesc ? db - da : da - db;
        });

        logsTableBody.innerHTML = '';
        if (filtered.length === 0) {
            logsTableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:2rem; color:var(--text-muted);">Aucun log trouvé.</td></tr>';
            return;
        }

        filtered.forEach(log => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-family:'Fira Code', monospace; font-size:0.85rem; color:var(--text-secondary);">${log.timestamp}</td>
                <td class="table-code" style="color:var(--accent-color); font-weight:600;">$ ${escapeHtml(log.command)}</td>
                <td style="text-align:center;">
                    <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem;" onclick="showLogDetails(${log.id})">👁️ Voir</button>
                </td>
            `;
            logsTableBody.appendChild(tr);
        });
    }

    if (logsSearchInput) logsSearchInput.addEventListener('input', renderLogs);
    if (logsSortBtn) logsSortBtn.addEventListener('click', () => {
        sortDesc = !sortDesc;
        const indicator = document.getElementById('sort-indicator');
        if(indicator) indicator.textContent = sortDesc ? "DESC ⬇️" : "ASC ⬆️";
        renderLogs();
    });

    // Fonction globale pour être appelée depuis le HTML onclick
    window.showLogDetails = function(id) {
        const log = allLogs.find(l => l.id === id);
        if (!log) return;
        if(logModalTitle) logModalTitle.textContent = log.command;
        if(logModalOutput) logModalOutput.textContent = log.output || "Aucune sortie.";
        if(logModal) logModal.classList.add('active');
    };

    if(closeLogModalBtn) closeLogModalBtn.onclick = () => logModal.classList.remove('active');
});