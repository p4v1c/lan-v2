/* static/js/checklist.js */

const DEFAULT_MANUAL_TARGET = "Manual"; // Special target for manually checked items

async function toggleChecklistItem(key, target, isChecked) {
    try {
        const res = await fetch('/api/checklist/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, target, is_checked: isChecked })
        });
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.error || 'Failed to toggle item');
        }
        return true;
    } catch (e) {
        console.error("Error toggling checklist item:", e);
        alert("Erreur: " + e.message);
        return false;
    }
}

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
            
            // Recalculate doneCount to include manual checks
            const doneCount = items.filter(item => {
                // An item is "done" if it has any target (auto) or if it's manually checked
                return item.targets.length > 0 || item.targets.includes(DEFAULT_MANUAL_TARGET);
            }).length;
            const totalCount = items.length;
            const percent = Math.round((doneCount / totalCount) * 100);

            const progressClass = percent === 100 ? 'completed' : '';

            let itemsHtml = '';
            for (const item of items) {
                // Determine if this item is considered "done" (either by a scan or manually)
                const isAutoChecked = item.targets.length > 0 && !item.targets.includes(DEFAULT_MANUAL_TARGET);
                const isManuallyChecked = item.targets.includes(DEFAULT_MANUAL_TARGET);
                const isOverallChecked = isAutoChecked || isManuallyChecked;

                const statusClass = isOverallChecked ? 'checked' : '';
                
                // Build target badges
                let targetsHtml = '';
                if (item.targets.length > 0) {
                    targetsHtml = item.targets.map(t => 
                        `<span class="target-badge">
                            <svg style="width:12px;height:12px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                            ${escapeHtml(t)}
                         </span>`
                    ).join('');
                }

                itemsHtml += `
                    <div class="checklist-item ${statusClass}" data-key="${escapeHtml(item.key)}">
                        <div class="status-indicator">
                            <input type="checkbox" class="manual-check-toggle" ${isOverallChecked ? 'checked' : ''} ${isAutoChecked ? 'disabled' : ''}>
                        </div>
                        
                        <div class="item-content">
                            <div class="item-header">
                                <div class="item-name">${escapeHtml(item.name)}</div>
                            </div>
                            <div class="item-desc">${escapeHtml(item.description)}</div>
                            ${item.targets.length > 0 ? `<div class="targets-container">${targetsHtml}</div>` : ''}
                        </div>
                    </div>
                `;
            }

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

        // Add event listeners after all items are rendered
        container.querySelectorAll('.manual-check-toggle').forEach(checkbox => {
            checkbox.addEventListener('change', async (event) => {
                const itemEl = event.target.closest('.checklist-item');
                const key = itemEl.dataset.key;
                const isChecked = event.target.checked;
                
                // Always use DEFAULT_MANUAL_TARGET for manual toggles
                const success = await toggleChecklistItem(key, DEFAULT_MANUAL_TARGET, isChecked);
                if (success) {
                    // Reload the checklist to update counts and statuses
                    await loadChecklist();
                } else {
                    // Revert checkbox state if API call failed
                    event.target.checked = !isChecked;
                }
            });
        });


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