document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. GESTION SCANNER
    // ==========================================
    let currentTabId = null;
    let allModules = [];
    let liveShellInterval = null;
    let tasksInterval = null;
    let selectedModuleForRun = null;
    let currentModeFilter = 'all'; // NOUVEAU : Filtre par défaut

    const modulesListEl = document.getElementById('modules-list');
    const moduleSearchEl = document.getElementById('module-search');
    const tabsContainer = document.getElementById('tabs-container');
    const tasksContainer = document.getElementById('active-tab-content');
    
    // Modals
    const configModal = document.getElementById('module-config-modal');
    const configTitle = document.getElementById('config-modal-title');
    const configInputs = document.getElementById('config-inputs-container');
    const confirmRunBtn = document.getElementById('confirm-run-btn');
    const cancelRunBtn = document.getElementById('cancel-run-btn');
    const closeConfigBtn = document.getElementById('close-config-modal');

    // ==========================================
    // GESTION DES VARIABLES GLOBALES
    // ==========================================
    const varsModal = document.getElementById('vars-modal');
    const varsListEl = document.getElementById('vars-list');
    const varsBtn = document.getElementById('global-vars-btn');
    const closeVarsBtn = document.getElementById('close-vars-modal');
    const addVarBtn = document.getElementById('add-var-btn');
    const newVarKey = document.getElementById('new-var-key');
    const newVarVal = document.getElementById('new-var-val');

    let globalVars = {}; 

    async function loadGlobalVars() {
        try {
            const r = await fetch('/api/vars');
            if (r.ok) {
                const data = await r.json();
                globalVars = data || {};
            } else {
                console.warn("API Vars non disponible (DB en cours de réinit ?)");
                globalVars = {};
            }
        } catch(e) {
            console.error("Erreur réseau vars", e);
            globalVars = {};
        }
        renderVars();
    }

    function renderVars() {
        if(!varsListEl) return;
        varsListEl.innerHTML = '';
        if (!globalVars || Object.keys(globalVars).length === 0) {
            varsListEl.innerHTML = '<div style="text-align:center; color:var(--text-secondary); font-style:italic;">Aucune variable définie.</div>';
            return;
        }
        for (const [key, val] of Object.entries(globalVars)) {
            const div = document.createElement('div');
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.alignItems = 'center';
            div.style.padding = '8px 12px';
            div.style.background = 'var(--bg-hover)';
            div.style.borderRadius = '6px';
            div.innerHTML = `
                <div>
                    <span style="font-weight:bold; color:var(--accent-color);">${escapeHtml(key)}</span>
                    <span style="color:var(--text-secondary); margin:0 5px;">=</span>
                    <span style="font-family:'Fira Code', monospace;">${escapeHtml(val)}</span>
                </div>
                <button onclick="deleteVar('${key}')" style="background:transparent; border:none; color:var(--danger); cursor:pointer;">&times;</button>
            `;
            varsListEl.appendChild(div);
        }
    }

    window.deleteVar = async (key) => {
        try { await fetch(`/api/vars/${key}`, {method:'DELETE'}); loadGlobalVars(); } catch(e){}
    };

    if(addVarBtn) addVarBtn.onclick = async () => {
        const k = newVarKey.value.trim();
        const v = newVarVal.value.trim();
        if(!k) return;
        try {
            await fetch('/api/vars', {
                method:'POST', 
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({key:k, value:v})
            });
            newVarKey.value = ''; newVarVal.value = '';
            loadGlobalVars();
        } catch(e) { alert("Erreur ajout variable"); }
    };

    if(varsBtn) varsBtn.onclick = () => { 
        loadGlobalVars(); 
        if(varsModal) varsModal.classList.add('active'); 
    };
    if(closeVarsBtn) closeVarsBtn.onclick = () => varsModal.classList.remove('active');

    // --- INITIALISATION ---
    if (modulesListEl && tabsContainer) {
        initScanner();
    }

    async function initScanner() {
        await loadGlobalVars(); 
        await loadModules();
        await loadTabs();
        tasksInterval = setInterval(() => {
            if(currentTabId) loadTasks(currentTabId);
        }, 2000);
    }

    // ==========================================
    // MODULES & CATEGORIES & FILTRES
    // ==========================================
    
    // Fonction appelée par les boutons HTML
    window.setModeFilter = function(mode) {
        currentModeFilter = mode;
        
        // Mise à jour visuelle des boutons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.innerText.toLowerCase() === mode || (mode === 'all' && btn.innerText === 'All')) {
                btn.classList.add('active');
            }
        });

        // Re-rendre la liste
        renderModulesList();
    };

    async function loadModules() {
        try {
            const res = await fetch('/api/modules');
            if(res.ok) {
                allModules = await res.json();
                renderModulesList();
            }
        } catch(e) { console.error("Erreur modules", e); }
    }

    function renderModulesList() {
        if(!modulesListEl) return;
        modulesListEl.innerHTML = '';
    
        const searchTerm = moduleSearchEl ? moduleSearchEl.value.toLowerCase() : '';
    
        const filtered = allModules.filter(mod => {
            const matchSearch = mod.name.toLowerCase().includes(searchTerm) || 
                                (mod.description && mod.description.toLowerCase().includes(searchTerm));
            
            let matchMode = true;
            if (currentModeFilter === 'manual') {
                matchMode = (mod.mode === 'manual');
            } else if (currentModeFilter === 'auto') {
                matchMode = (mod.mode === 'auto');
            }
            
            return matchSearch && matchMode;
        });
    
        if(filtered.length === 0) {
            modulesListEl.innerHTML = '<div style="padding:15px; text-align:center; color:var(--text-secondary); font-style:italic;">Aucun module trouvé.</div>';
            return;
        }
    
        const groupedByCategory = filtered.reduce((acc, mod) => {
            const category = mod.category || 'Autre';
            if (!acc[category]) {
                acc[category] = [];
            }
            acc[category].push(mod);
            return acc;
        }, {});
    
        const sortedCategories = Object.keys(groupedByCategory).sort();
    
        sortedCategories.forEach(category => {
            const details = document.createElement('details');
            details.open = false; 
    
            const summary = document.createElement('summary');
            summary.innerHTML = `<span>${escapeHtml(category)}</span> <span class="badge">${groupedByCategory[category].length}</span>`;
            details.appendChild(summary);
    
            const categoryContent = document.createElement('div');
            categoryContent.className = 'module-category-content';
            
            groupedByCategory[category].forEach(mod => {
                const div = document.createElement('div');
                div.className = 'module-item';
                
                const modeBadge = mod.mode === 'auto' ? '<span class="badge" style="background:#8b5cf6; color:white; margin-left:5px; font-size:0.5rem;">AUTO</span>' : '';
    
                div.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-weight:600; color:var(--text-primary);">
                            ${escapeHtml(mod.name)}
                            ${modeBadge}
                        </div>
                    </div>
                    <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:2px;">${escapeHtml(mod.description || '')}</div>
                `;
                
                div.onclick = () => openConfigModal(mod);
                categoryContent.appendChild(div);
            });
    
            details.appendChild(categoryContent);
            modulesListEl.appendChild(details);
        });
    }

    if (moduleSearchEl) {
        moduleSearchEl.addEventListener('input', () => {
            renderModulesList();
        });
    }

    // --- CONFIG MODAL & RUN ---
    function openConfigModal(module) {
        if (!currentTabId) { alert("Créez d'abord un onglet à droite."); return; }
        selectedModuleForRun = module;
        configTitle.textContent = `Ajouter : ${module.name}`;
        confirmRunBtn.textContent = "✚ Ajouter au scan";
        
        configInputs.innerHTML = '';
        configModal.classList.add('active');

        if (module.inputs) {
            module.inputs.forEach(inp => {
                const prefillValue = (globalVars && globalVars[inp.name]) || inp.default || '';
                const wrapper = document.createElement('div');
                wrapper.innerHTML = `
                    <label style="display:block; font-size:0.9rem; color:var(--text-secondary);">
                        ${inp.label}
                        ${(globalVars && globalVars[inp.name]) ? '<span class="badge badge-info" style="font-size:0.6rem; margin-left:5px;">GLOBAL</span>' : ''}
                    </label>
                    <input type="text" class="run-input" data-key="${inp.name}" value="${prefillValue}" 
                           placeholder="${inp.placeholder || ''}" 
                           style="width:100%; padding:8px; border-radius:6px; border:1px solid var(--bg-separator); background:var(--bg-body); color:var(--text-primary);">
                `;
                configInputs.appendChild(wrapper);
            });
        }
    }

    function closeConfig() {
        configModal.classList.remove('active');
        selectedModuleForRun = null;
    }
    if(closeConfigBtn) closeConfigBtn.onclick = closeConfig;
    if(cancelRunBtn) cancelRunBtn.onclick = closeConfig;

    if(confirmRunBtn) confirmRunBtn.onclick = async () => {
        if(!selectedModuleForRun || !currentTabId) return;
        const inputs = {};
        document.querySelectorAll('.run-input').forEach(i => inputs[i.dataset.key] = i.value);

        try {
            const res = await fetch('/api/tasks/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    tab_id: currentTabId,
                    module_id: selectedModuleForRun.id,
                    inputs: inputs
                })
            });
            
            const data = await res.json();
            
            if (!res.ok || data.error) {
                alert("Erreur serveur: " + (data.error || res.statusText));
            } else {
                closeConfig();
                loadTasks(currentTabId);
            }
        } catch(e) { 
            alert("Erreur communication : " + e); 
        }
    };

    // --- TABS ---
    async function loadTabs() {
        try {
            const res = await fetch('/api/tabs');
            if(!res.ok) throw new Error("API Tabs Error");
            const tabs = await res.json();
            
            if(tabsContainer) {
                tabsContainer.innerHTML = '';

                tabs.forEach(tab => {
                    const tabEl = document.createElement('div');
                    tabEl.className = `tab-group ${currentTabId === tab.id ? 'active' : ''}`;
                    tabEl.innerHTML = `<span class="tab-name">${escapeHtml(tab.name)}</span><span class="tab-close">&times;</span>`;
                    tabEl.onclick = () => switchTab(tab.id);
                    tabEl.querySelector('.tab-name').ondblclick = (e) => renameTab(e, tab);
                    tabEl.querySelector('.tab-close').onclick = (e) => closeTab(e, tab);
                    tabsContainer.appendChild(tabEl);
                });
                
                const addBtn = document.createElement('button');
                addBtn.className = 'tab-add-btn';
                addBtn.innerHTML = '+';
                addBtn.onclick = createNewTab;
                tabsContainer.appendChild(addBtn);

                if (!currentTabId && tabs.length > 0) switchTab(tabs[0].id);
            }
        } catch(e) { console.error("Erreur chargement tabs:", e); }
    }

    async function createNewTab() {
        try {
            const r = await fetch('/api/tabs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:'Scan'})});
            if (r.ok) {
                const d = await r.json();
                if (d && d.id) {
                    switchTab(d.id);
                } else {
                    alert("Impossible de créer l'onglet (Erreur DB).");
                }
            } else {
                alert("Erreur serveur lors de la création.");
            }
        } catch(e) { 
            console.error(e);
            alert("Erreur connexion serveur.");
        }
    }

    function switchTab(tid) { 
        if(!tid) return;
        currentTabId = tid; 
        loadTabs(); 
        loadTasks(tid); 
    }
    
    async function renameTab(e, tab) { 
        e.stopPropagation(); 
        const n=prompt("Nom:", tab.name); 
        if(n) { 
            try { await fetch(`/api/tabs/${tab.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n})}); loadTabs(); } catch(e){}
        } 
    }
    
    async function closeTab(e, tab) { 
        e.stopPropagation(); 
        if(confirm("Fermer l'onglet ?")) { 
            try { await fetch(`/api/tabs/${tab.id}`, {method:'DELETE'}); if(currentTabId===tab.id) currentTabId=null; loadTabs(); } catch(e){}
        } 
    }

    // --- TASKS ---
    async function loadTasks(tabId) {
        if(!tabId) return;
        try {
            const res = await fetch(`/api/tabs/${tabId}/tasks`);
            if(res.ok) {
                const tasks = await res.json();
                tasksContainer.innerHTML = '';

                if(tasks.length === 0) {
                    tasksContainer.innerHTML = '<div style="padding:2rem;text-align:center;color:#64748B;">Aucune tâche. Ajoutez-en une depuis la gauche.</div>';
                    return;
                }

                tasks.forEach(task => {
                    const div = document.createElement('div');
                    div.style.borderBottom = '1px solid #333';
                    div.style.padding = '12px 15px';
                    div.style.display = 'flex';
                    div.style.justifyContent = 'space-between';
                    div.style.alignItems = 'center';
                    
                    let statusBadge = '';
                    let actionBtns = '';

                    if (task.status === 'pending') {
                        statusBadge = `<span class="badge" style="background:#475569; color:#E2E8F0;">⏸ PENDING</span>`;
                        actionBtns = `
                            <button class="btn" style="padding:4px 12px; font-size:0.8rem; background:var(--success); color:white;" onclick="startTask(${task.id})">▶ Start</button>
                            <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem; color:#EF4444; border-color:#EF4444; margin-left:5px;" onclick="deleteTask(${task.id})">🗑</button>
                        `;
                    } 
                    else if (task.status === 'running') {
                        statusBadge = `<span class="badge badge-warning">⏳ RUNNING</span>`;
                        actionBtns = `
                            <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem; color:#EF4444; border-color:#EF4444;" onclick="stopTask(${task.id})">⏹ Stop</button>
                            <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem; margin-left:5px;" onclick="openLiveShell(${task.id}, '${task.module}')">📺 Shell</button>
                        `;
                    } 
                    else {
                        let color = task.status === 'completed' ? 'badge-success' : 'badge-danger';
                        statusBadge = `<span class="badge ${color}">${task.status.toUpperCase()}</span>`;
                        actionBtns = `
                            <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem;" onclick="openLiveShell(${task.id}, '${task.module}')">📺 Logs</button>
                            <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem; color:#EF4444; border-color:#333; margin-left:5px;" onclick="deleteTask(${task.id})">🗑</button>
                        `;
                    }

                    div.innerHTML = `
                        <div style="flex:1;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                ${statusBadge}
                                <span style="font-weight:bold; color:#E2E8F0;">${escapeHtml(task.module)}</span>
                                <span style="font-size:0.8rem; color:#64748B;">${task.time || ''}</span>
                            </div>
                            <div style="font-family:'Fira Code', monospace; color:#94A3B8; font-size:0.85rem; margin-top:4px;">$ ${escapeHtml(task.cmd)}</div>
                        </div>
                        <div>${actionBtns}</div>
                    `;
                    tasksContainer.appendChild(div);
                });
            }
        } catch(e) {}
    }

    window.startTask = async (tid) => { 
        try { 
            const response = await fetch(`/api/tasks/${tid}/start`, {method:'POST'}); 
            const data = await response.json();
            if (data.error) alert("Erreur : " + data.error);
            else loadTasks(currentTabId); 
        } catch(e) { alert("Erreur communication"); } 
    };

    window.stopTask = async (tid) => { if(!confirm("Arrêter ?")) return; await fetch(`/api/tasks/${tid}/stop`, {method:'POST'}); loadTasks(currentTabId); };
    window.deleteTask = async (tid) => { if(!confirm("Supprimer ?")) return; await fetch(`/api/tasks/${tid}`, {method:'DELETE'}); loadTasks(currentTabId); };

    // --- LIVE SHELL ---
    const liveModal = document.getElementById('live-shell-modal');
    const liveOutput = document.getElementById('live-shell-output');
    const closeLiveBtn = document.getElementById('close-live-shell');

    window.openLiveShell = function(taskId, name) {
        if(liveModal) {
            liveModal.classList.add('active');
            liveOutput.textContent = "Chargement...";
            if(liveShellInterval) clearInterval(liveShellInterval);
            
            const poll = async () => {
                try {
                    const res = await fetch(`/api/tasks/${taskId}/output`);
                    const d = await res.json();
                    if(liveOutput.textContent !== d.output) {
                        liveOutput.textContent = d.output;
                        liveOutput.scrollTop = liveOutput.scrollHeight;
                    }
                } catch(e){}
            };
            poll();
            liveShellInterval = setInterval(poll, 1000);
        }
    };

    if(closeLiveBtn) closeLiveBtn.onclick = () => {
        liveModal.classList.remove('active');
        if(liveShellInterval) clearInterval(liveShellInterval);
    };

    // --- WEBSHELL GLOBAL ---
    const fabBtn = document.getElementById('webshell-toggle');
    const drawer = document.getElementById('webshell-container');
    const closeDrawerBtn = document.getElementById('webshell-close');
    const expandBtn = document.getElementById('webshell-expand');
    const termInput = document.getElementById('terminal-input');
    const termOutput = document.getElementById('terminal-output');

    if (fabBtn && drawer) {
        fabBtn.addEventListener('click', () => {
            drawer.classList.toggle('open');
            if (drawer.classList.contains('open') && termInput) setTimeout(() => termInput.focus(), 100);
        });
    }

    if (expandBtn) {
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            drawer.classList.toggle('maximized');
            expandBtn.textContent = drawer.classList.contains('maximized') ? '❐' : '⛶';
        });
    }

    if (closeDrawerBtn) {
        closeDrawerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            drawer.classList.remove('open');
            drawer.classList.remove('maximized');
            if(expandBtn) expandBtn.textContent = '⛶';
        });
    }
    
    if (termInput && termOutput) {
        termInput.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter') {
                const cmd = termInput.value.trim();
                if (!cmd) return;
                if (cmd === 'clear') { termOutput.innerHTML = ''; termInput.value = ''; return; }
                
                termOutput.innerHTML += `<div style="color:#A0AEC0;font-weight:bold;">$ ${escapeHtml(cmd)}</div>`;
                termInput.value = '';

                try {
                    const r = await fetch('/api/shell', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({cmd})});
                    const d = await r.json();
                    termOutput.innerHTML += `<div>${escapeHtml(d.output)}</div>`;
                    termOutput.scrollTop = termOutput.scrollHeight;
                } catch(e) {}
            }
        });
    }

    // --- THEME ---
    const themeBtn = document.getElementById('theme-toggle');
    const body = document.body;
    const currentTheme = localStorage.getItem('theme') || 'light';
    body.setAttribute('data-theme', currentTheme);
    if (themeBtn) themeBtn.addEventListener('click', () => {
        const newTheme = body.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });

    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
});