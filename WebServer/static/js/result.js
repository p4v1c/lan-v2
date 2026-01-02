
document.addEventListener('DOMContentLoaded', () => {
    const resultsSummaryContent = document.getElementById('results-summary-content');
    const ipDetailsContent = document.getElementById('ip-details-content');
    const detailPanelTitle = document.getElementById('detail-panel-title');
    const refreshButton = document.getElementById('refresh-summary');

    let currentActiveIpItem = null;
    let lastSelectedIpData = null;
    const severityOrder = { "CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0 };

    const getSeverityClass = (severity) => {
        if (!severity) return 'info';
        const s = severity.toUpperCase();
        if (s.includes("CRITICAL")) return 'critical';
        if (s.includes("HIGH")) return 'high';
        if (s.includes("MEDIUM")) return 'medium';
        if (s.includes("LOW")) return 'low';
        return 'info';
    };

    const fetchAndRenderSummary = async () => {
        if (!resultsSummaryContent) return;
        resultsSummaryContent.innerHTML = '<div class="no-results-message">Chargement...</div>';
        
        try {
            const res = await fetch('/api/results/host-summary');
            if (!res.ok) throw new Error(`Erreur HTTP: ${res.status}`);
            const summary = await res.json();
            renderVulnerabilitySummary(summary);
            
            if (lastSelectedIpData) {
                const updatedIpData = findIpDataInSummary(summary, lastSelectedIpData.ip);
                if (updatedIpData) {
                    lastSelectedIpData = updatedIpData;
                    displayIpDetails(updatedIpData);
                } else {
                    detailPanelTitle.textContent = 'Sélectionnez un Hôte';
                    ipDetailsContent.innerHTML = '<div class="no-results-message">Cet hôte n\'a plus de données.</div>';
                    lastSelectedIpData = null;
                }
            }
        } catch (e) {
            resultsSummaryContent.innerHTML = `<div class="no-results-message">Erreur: ${e.message}</div>`;
        }
    };
    
    const findIpDataInSummary = (summaryData, ip) => {
        for (const subnet in summaryData) {
            const found = summaryData[subnet].find(ipData => ipData.ip === ip);
            if (found) return found;
        }
        return null;
    };

    const renderVulnerabilitySummary = (summaryData) => {
        resultsSummaryContent.innerHTML = '';
        if (Object.keys(summaryData).length === 0) {
            resultsSummaryContent.innerHTML = `<div class="no-results-message">Aucun hôte trouvé.</div>`;
            return;
        }

        Object.keys(summaryData).sort().forEach(subnet => {
            const subnetGroup = document.createElement('div');
            subnetGroup.className = 'subnet-group';
            const details = document.createElement('details');
            details.open = true;
            const summary = document.createElement('summary');
            summary.innerHTML = `<span>${escapeHtml(subnet)}</span>`;
            details.appendChild(summary);
            
            const subnetIpsContainer = document.createElement('div');
            subnetIpsContainer.className = 'subnet-ips';
            details.appendChild(subnetIpsContainer);

            summaryData[subnet].sort((a,b) => {
                const ipA = a.ip.split('.').map(Number);
                const ipB = b.ip.split('.').map(Number);
                for (let i = 0; i < 4; i++) { if (ipA[i] !== ipB[i]) return ipA[i] - ipB[i]; }
                return 0;
            }).forEach(ipData => {
                const ipItem = document.createElement('div');
                ipItem.className = 'ip-item';
                if (lastSelectedIpData && ipData.ip === lastSelectedIpData.ip) {
                    ipItem.classList.add('active');
                    currentActiveIpItem = ipItem;
                }
                
                const leftContent = document.createElement('div');
                leftContent.className = 'ip-item-left';
                const hostnameDisplay = ipData.hostname ? `<span class="hostname">(${escapeHtml(ipData.hostname)})</span>` : '';
                leftContent.innerHTML = `<span>${escapeHtml(ipData.ip)}</span> ${hostnameDisplay}`;

                const vulnCountSpan = document.createElement('span');
                vulnCountSpan.className = 'vuln-count';
                vulnCountSpan.textContent = ipData.vuln_count;

                ipItem.appendChild(leftContent);
                ipItem.appendChild(vulnCountSpan);
                subnetIpsContainer.appendChild(ipItem);

                ipItem.addEventListener('click', () => {
                    if (currentActiveIpItem) currentActiveIpItem.classList.remove('active');
                    ipItem.classList.add('active');
                    currentActiveIpItem = ipItem;
                    lastSelectedIpData = ipData;
                    displayIpDetails(ipData);
                });
            });

            subnetGroup.appendChild(details);
            resultsSummaryContent.appendChild(subnetGroup);
        });
    };

    const displayIpDetails = (ipData) => {
        let title = ipData.ip;
        if (ipData.hostname) title += ` - ${ipData.hostname}`;
        detailPanelTitle.textContent = title;
        ipDetailsContent.innerHTML = '';

        // --- Vulnerabilities Section ---
        const vulnsSection = document.createElement('div');
        vulnsSection.className = 'detail-section';
        vulnsSection.innerHTML = `<div class="detail-section-header"><span>Vulnérabilités (${ipData.vulnerabilities.length})</span></div>`;
        const vulnListContainer = document.createElement('div');
        vulnListContainer.className = 'vulnerability-list';
        
        if (ipData.vulnerabilities.length === 0) {
            vulnListContainer.innerHTML = `<div class="no-results-message">Aucune vulnérabilité.</div>`;
        } else {
            ipData.vulnerabilities.sort((a, b) => (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0))
            .forEach(vuln => {
                const vulnEntry = document.createElement('div');
                vulnEntry.className = 'vulnerability-entry';
                const summary = document.createElement('div');
                summary.className = 'vuln-summary';
                summary.innerHTML = `
                    <span class="vuln-title">${escapeHtml(vuln.title)}</span>
                    <div>
                        <span class="vuln-severity ${getSeverityClass(vuln.severity)}">${escapeHtml(vuln.severity)}</span>
                        <button class="delete-btn" data-vuln-id="${vuln.id}" title="Supprimer la vulnérabilité">🗑️</button>
                        <button class="vuln-details-toggle"></button>
                    </div>`;
                
                const details = document.createElement('div');
                details.className = 'vuln-full-details';
                details.innerHTML = `<p><strong>Module:</strong> ${escapeHtml(vuln.module)}</p>
                                     <p><strong>Date:</strong> ${escapeHtml(vuln.date)}</p>
                                     <p>${escapeHtml(vuln.details)}</p>`;

                vulnEntry.appendChild(summary);
                vulnEntry.appendChild(details);
                vulnListContainer.appendChild(vulnEntry);

                summary.querySelector('.vuln-details-toggle').addEventListener('click', (e) => {
                    e.stopPropagation();
                    const detailsDiv = e.currentTarget.closest('.vulnerability-entry').querySelector('.vuln-full-details');
                    detailsDiv.style.display = detailsDiv.style.display === 'block' ? 'none' : 'block';
                });
            });
        }
        vulnsSection.appendChild(vulnListContainer);
        ipDetailsContent.appendChild(vulnsSection);

        // --- Scans Section ---
        const scansSection = document.createElement('div');
        scansSection.className = 'detail-section';
        scansSection.innerHTML = `<div class="detail-section-header"><span>Modules Exécutés (${ipData.scans.length})</span></div>`;
        const scanListContainer = document.createElement('div');
        scanListContainer.className = 'vulnerability-list';
        
        if (ipData.scans.length === 0) {
            scanListContainer.innerHTML = `<div class="no-results-message">Aucun module exécuté.</div>`;
        } else {
            ipData.scans.sort((a, b) => new Date(b.date) - new Date(a.date))
            .forEach(scan => {
                const scanEntry = document.createElement('div');
                scanEntry.className = 'vulnerability-entry';
                const summary = document.createElement('div');
                summary.className = 'vuln-summary';
                summary.innerHTML = `
                    <span class="vuln-title">${escapeHtml(scan.module)}</span>
                    <div>
                        <span class="scan-date">${escapeHtml(scan.date)}</span>
                        <button class="delete-btn" data-scan-id="${scan.id}" title="Supprimer ce scan">🗑️</button>
                        <button class="vuln-details-toggle"></button>
                    </div>`;

                const details = document.createElement('div');
                details.className = 'vuln-full-details';
                details.innerHTML = `<pre>Chargement du résultat...</pre>`;
                
                scanEntry.appendChild(summary);
                scanEntry.appendChild(details);
                scanListContainer.appendChild(scanEntry);

                summary.querySelector('.vuln-details-toggle').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const detailsDiv = e.currentTarget.closest('.vulnerability-entry').querySelector('.vuln-full-details');
                    const isVisible = detailsDiv.style.display === 'block';

                    if (!isVisible && !detailsDiv.dataset.loaded) {
                        try {
                            const res = await fetch(`/api/tasks/${scan.id}/output`);
                            const data = await res.json();
                            detailsDiv.innerHTML = `<pre>${escapeHtml(data.output || 'Aucun résultat.')}</pre>`;
                            detailsDiv.dataset.loaded = 'true';
                        } catch (err) {
                            detailsDiv.innerHTML = `<pre>Erreur: ${err.message}</pre>`;
                        }
                    }
                    detailsDiv.style.display = isVisible ? 'none' : 'block';
                });
            });
        }
        scansSection.appendChild(scanListContainer);
        ipDetailsContent.appendChild(scansSection);

        // Add event listeners for delete buttons
        ipDetailsContent.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                e.stopPropagation();
                const vulnId = e.currentTarget.dataset.vulnId;
                const scanId = e.currentTarget.dataset.scanId;
                
                if (vulnId) {
                    if (confirm('Êtes-vous sûr de vouloir supprimer cette vulnérabilité ?')) {
                        await deleteItem('vuln', vulnId);
                    }
                } else if (scanId) {
                    if (confirm('Êtes-vous sûr de vouloir supprimer ce scan ?')) {
                        await deleteItem('scan', scanId);
                    }
                }
            });
        });
    };
    
    const deleteItem = async (type, id) => {
        const url = type === 'vuln' ? `/api/vulns/${id}` : `/api/tasks/${id}`;
        try {
            const res = await fetch(url, { method: 'DELETE' });
            if (!res.ok) throw new Error(`Erreur lors de la suppression.`);
            await fetchAndRenderSummary();
        } catch (err) {
            alert(`Erreur: ${err.message}`);
        }
    };

    const escapeHtml = (str) => {
        const p = document.createElement('p');
        p.appendChild(document.createTextNode(str || ''));
        return p.innerHTML;
    };

    fetchAndRenderSummary();
    if (refreshButton) {
        refreshButton.addEventListener('click', fetchAndRenderSummary);
    }
});