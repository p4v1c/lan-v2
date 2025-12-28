/* static/js/result.js */

document.addEventListener('DOMContentLoaded', () => {
    const resultsSummaryContent = document.getElementById('results-summary-content');
    const ipDetailsContent = document.getElementById('ip-details-content');
    const detailPanelTitle = document.getElementById('detail-panel-title');
    const refreshButton = document.getElementById('refresh-summary');

    let currentActiveIpItem = null;
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

    const createSeverityDots = (highestSeverity, vulnCounts) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'severity-dots';
        const severities = ['critical', 'high', 'medium', 'low'];
        let dotsAdded = 0;

        for (const sev of severities) {
            if (dotsAdded < 3 && vulnCounts[sev.toUpperCase()] > 0) {
                const dot = document.createElement('span');
                dot.className = `severity-dot ${sev}`;
                wrapper.appendChild(dot);
                dotsAdded++;
            }
        }
        // If no vulns but we want to show something, can add logic here.
        // For now, no dots if no vulns.
        return wrapper;
    };
    
    const fetchAndRenderSummary = async () => {
        if (!resultsSummaryContent) return;
        resultsSummaryContent.innerHTML = '<div class="no-results-message">Chargement...</div>';
        
        try {
            const res = await fetch('/api/results/host-summary');
            if (!res.ok) throw new Error(`Erreur HTTP: ${res.status}`);
            const summary = await res.json();
            renderVulnerabilitySummary(summary);
        } catch (e) {
            resultsSummaryContent.innerHTML = `<div class="no-results-message">Erreur: ${e.message}</div>`;
        }
    };

    const renderVulnerabilitySummary = (summaryData) => {
        resultsSummaryContent.innerHTML = '';

        if (Object.keys(summaryData).length === 0) {
            resultsSummaryContent.innerHTML = `
                <div class="no-results-message">
                    <svg class="icon-xl" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span>Aucun hôte trouvé. Lancez des scans pour voir les résultats.</span>
                </div>`;
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
                for (let i = 0; i < 4; i++) {
                    if (ipA[i] !== ipB[i]) return ipA[i] - ipB[i];
                }
                return 0;
            }).forEach(ipData => {
                const ipItem = document.createElement('div');
                ipItem.className = 'ip-item';
                
                const leftContent = document.createElement('div');
                leftContent.className = 'ip-item-left';
                leftContent.innerHTML = `<span>${escapeHtml(ipData.ip)}</span>`;
                if(ipData.vuln_count > 0) {
                    leftContent.prepend(createSeverityDots(ipData.highest_severity, ipData.severity_counts));
                }

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
                    displayIpDetails(ipData);
                });
            });

            subnetGroup.appendChild(details);
            resultsSummaryContent.appendChild(subnetGroup);
        });
    };

    const displayIpDetails = (ipData) => {
        detailPanelTitle.textContent = ipData.ip;
        ipDetailsContent.innerHTML = '';

        // --- Vulnerabilities Section ---
        const vulnsSection = document.createElement('div');
        vulnsSection.className = 'detail-section';
        vulnsSection.innerHTML = `<div class="detail-section-header">
            <svg class="icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span>Vulnérabilités (${ipData.vulnerabilities.length})</span>
        </div>`;
        const vulnListContainer = document.createElement('div');
        vulnListContainer.className = 'vulnerability-list';
        
        if (ipData.vulnerabilities.length === 0) {
            vulnListContainer.innerHTML = `<div class="no-results-message">Aucune vulnérabilité trouvée pour cet hôte.</div>`;
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
                    const btn = e.target;
                    const detailsDiv = btn.closest('.vulnerability-entry').querySelector('.vuln-full-details');
                    const isVisible = detailsDiv.style.display === 'block';
                    detailsDiv.style.display = isVisible ? 'none' : 'block';
                    btn.textContent = isVisible ? '' : '';
                });
            });
        }
        vulnsSection.appendChild(vulnListContainer);
        ipDetailsContent.appendChild(vulnsSection);

        // --- Scans Section ---
        const scansSection = document.createElement('div');
        scansSection.className = 'detail-section';
        scansSection.innerHTML = `<div class="detail-section-header">
            <svg class="icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            <span>Modules Exécutés (${ipData.scans.length})</span>
        </div>`;
        const scanListContainer = document.createElement('div');
        scanListContainer.className = 'scan-list';
        
        if (ipData.scans.length === 0) {
            scanListContainer.innerHTML = `<div class="no-results-message">Aucun module n'a été exécuté sur cet hôte.</div>`;
        } else {
            ipData.scans.sort((a, b) => new Date(b.date) - new Date(a.date))
            .forEach(scan => {
                const scanEntry = document.createElement('div');
                scanEntry.className = 'scan-entry';
                scanEntry.innerHTML = `<span class="scan-module">${escapeHtml(scan.module)}</span>
                                     <span class="scan-date">${escapeHtml(scan.date)}</span>`;
                scanListContainer.appendChild(scanEntry);
            });
        }
        scansSection.appendChild(scanListContainer);
        ipDetailsContent.appendChild(scansSection);
    };
    
    const escapeHtml = (str) => {
        const p = document.createElement('p');
        p.appendChild(document.createTextNode(str));
        return p.innerHTML;
    };

    fetchAndRenderSummary();
    if (refreshButton) {
        refreshButton.addEventListener('click', fetchAndRENderSummary);
    }
});