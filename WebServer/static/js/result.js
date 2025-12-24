/* static/js/result.js */
document.addEventListener('DOMContentLoaded', () => {
    const treeContent = document.getElementById('results-tree-content');
    const logViewerContent = document.getElementById('log-viewer-content');
    const logViewerTitle = document.getElementById('log-viewer-title');

    async function refreshResultsTree() {
        if (!treeContent) return;
        treeContent.innerHTML = '<div>Chargement...</div>';
        try {
            const res = await fetch('/api/results/tree');
            const tree = await res.json();
            renderTree(tree);
        } catch(e) { treeContent.innerHTML = 'Erreur'; }
    }

    function renderTree(tree) {
        treeContent.innerHTML = '';
        Object.keys(tree).sort().forEach(subnet => {
            const det = document.createElement('details'); det.open = true;
            det.innerHTML = `<summary>🌐 ${escapeHtml(subnet)}</summary>`;
            const subDiv = document.createElement('div'); subDiv.className = 'tree-child';
            
            Object.keys(tree[subnet]).sort().forEach(ip => {
                const ipDet = document.createElement('details');
                ipDet.innerHTML = `<summary>💻 ${escapeHtml(ip)}</summary>`;
                const ipDiv = document.createElement('div'); ipDiv.className = 'tree-child';
                
                tree[subnet][ip].forEach(task => {
                    const item = document.createElement('div');
                    item.className = 'result-item';
                    item.innerHTML = `<span>${escapeHtml(task.module)}</span> <button onclick="deleteResult(event, ${task.id})" style="border:none;background:none;color:red;">🗑</button>`;
                    item.onclick = (e) => {
                        if(e.target.tagName !== 'BUTTON') loadResultLog(task.id, task.module);
                    };
                    ipDiv.appendChild(item);
                });
                ipDet.appendChild(ipDiv);
                subDiv.appendChild(ipDet);
            });
            det.appendChild(subDiv);
            treeContent.appendChild(det);
        });
    }

    async function loadResultLog(id, name) {
        logViewerTitle.textContent = name;
        logViewerContent.textContent = "Chargement...";
        let url = `/api/tasks/${id}/output`;
        if(name.includes("[")) url = `/api/vulns/${id}/details`;
        const res = await fetch(url);
        const d = await res.json();
        logViewerContent.textContent = d.output;
    }

    window.deleteResult = async (e, id) => {
        e.stopPropagation();
        if(confirm("Supprimer ?")) { await fetch(`/api/tasks/${id}`, {method:'DELETE'}); refreshResultsTree(); }
    };

    window.refreshResultsTree = refreshResultsTree; // Expose global
    refreshResultsTree();
});