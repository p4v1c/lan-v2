/* static/js/checklist.js */

async function loadChecklist() {
    const container = document.getElementById('checklist-wrapper');
    if(!container) return;

    try {
        container.innerHTML = '<div style="text-align:center; padding:3rem; color:grey">Chargement...</div>';
        
        const res = await fetch('/api/checklist');
        const data = await res.json();
        
        container.innerHTML = '';
        if (Object.keys(data).length === 0) {
            container.innerHTML = '<div style="text-align:center; padding:3rem;">Aucune donnée.</div>';
            return;
        }

        const sortedCats = Object.keys(data).sort();

        for (const cat of sortedCats) {
            const items = data[cat];
            const doneCount = items.filter(i => i.targets.length > 0).length;
            const totalCount = items.length;
            const percent = Math.round((doneCount / totalCount) * 100);

            // Classe CSS pour la couleur de la barre
            const progressClass = percent === 100 ? 'completed' : '';

            let itemsHtml = '';
            items.forEach(item => {
                const isDone = item.targets.length > 0;
                const statusClass = isDone ? 'checked' : '';
                
                // Badges
                const targetsHtml = item.targets.map(t => 
                    `<span class="target-badge">
                        <svg style="width:12px;height:12px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        ${escapeHtml(t)}
                     </span>`
                ).join('');

                itemsHtml += `
                    <div class="checklist-item">
                        <div class="status-indicator ${statusClass}">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        </div>
                        
                        <div class="item-content">
                            <div class="item-header">
                                <div class="item-name">${escapeHtml(item.name)}</div>
                            </div>
                            <div class="item-desc">${escapeHtml(item.description)}</div>
                            ${isDone ? `<div class="targets-container">${targetsHtml}</div>` : ''}
                        </div>
                    </div>
                `;
            });

            // Construction de la Section Catégorie
            const section = document.createElement('div');
            section.className = 'category-section';
            section.innerHTML = `
                <div class="category-header">
                    <div class="cat-title">
                        ${escapeHtml(cat)}
                    </div>
                    <div class="cat-stats">
                        ${doneCount} / ${totalCount}
                    </div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill ${progressClass}" style="width: ${percent}%"></div>
                </div>
                <div class="items-list">
                    ${itemsHtml}
                </div>
            `;
            container.appendChild(section);
        }

    } catch(e) {
        console.error(e);
        container.innerHTML = '<div style="color:red; text-align:center; padding:2rem">Erreur chargement checklist</div>';
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

document.addEventListener('DOMContentLoaded', loadChecklist);