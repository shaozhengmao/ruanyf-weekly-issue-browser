/**
 * 阮一峰周刊 Issue 浏览器
 * Pure vanilla JS — no frameworks, no dependencies.
 * Supports two-level category filtering.
 */

(function () {
    'use strict';

    // ===== Config =====
    const PAGE_SIZE = 30;
    const SEARCH_DEBOUNCE_MS = 250;
    const DATA_URL = 'data/issues.json';

    // Category colors (matches Python script)
    const CATEGORY_COLORS = {
        '开源项目': { bg: 'rgba(88,166,255,0.15)', text: '#58a6ff' },
        '工具':     { bg: 'rgba(240,136,62,0.15)', text: '#f0883e' },
        '产品':     { bg: 'rgba(163,113,247,0.15)', text: '#a371f7' },
        '投稿推荐': { bg: 'rgba(210,153,34,0.15)', text: '#d29922' },
        '讨论/反馈': { bg: 'rgba(139,148,158,0.12)', text: '#8b949e' },
    };

    const CATEGORY_ICONS = {
        '开源项目': '📦', '工具': '🔧', '产品': '🚀',
        '投稿推荐': '📮', '讨论/反馈': '💬',
    };

    // ===== State =====
    let allIssues = [];
    let filteredIssues = [];
    let displayedCount = 0;
    let currentCategory = 'all';
    let currentSubcategory = 'all';
    let currentMonth = 'all';
    let searchQuery = '';
    let searchIndex = null;
    let isLoading = false;
    let dataLoaded = false;

    // Subcategory metadata from server data
    let subcatMeta = {};
    // Per-category subcategory counts (computed after data load)
    let subcatCounts = {}; // { "开源项目": { "AI/LLM": 42, ... }, ... }

    // ===== DOM refs =====
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        searchInput: $('#searchInput'),
        statsTotal: $('#statTotal'),
        statsMonth: $('#statMonth'),
        statsWeek: $('#statWeek'),
        statsFeatured: $('#statFeatured'),
        categoryTabs: $('#categoryTabs'),
        subcatTabs: $('#subcatTabs'),
        subfilters: $('#subfilters'),
        monthFilter: $('#monthFilter'),
        issueList: $('#issueList'),
        loading: $('#loading'),
        emptyState: $('#emptyState'),
        backToTop: $('#backToTop'),
        lastUpdated: $('#lastUpdated'),
        resetFilters: $('#resetFilters'),
        countAll: $('#countAll'),
    };

    // ===== Data Loading =====
    async function loadData() {
        try {
            dom.loading.style.display = 'block';
            const resp = await fetch(DATA_URL);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            allIssues = data.issues || [];
            dataLoaded = true;

            // Subcategory metadata
            subcatMeta = (data.meta && data.meta.subcategory_meta) ||
                         (data.stats && data.stats.subcategory_meta) || {};

            // Update stats
            const stats = data.stats || {};
            dom.statsTotal.textContent = formatNumber(stats.total || allIssues.length);
            dom.statsMonth.textContent = formatNumber(stats.this_month || 0);
            dom.statsWeek.textContent = formatNumber(stats.this_week || 0);
            dom.statsFeatured.textContent = formatNumber(stats.featured || 0);

            if (data.meta && data.meta.generated_at) {
                dom.lastUpdated.textContent = formatDate(data.meta.generated_at);
            }

            // Compute subcategory counts per category
            computeSubcatCounts();

            // Build UI
            buildCategoryTabs(stats.by_category || {});
            buildMonthFilter();

            // Build search index async
            if (window.requestIdleCallback) {
                requestIdleCallback(() => buildSearchIndex());
            } else {
                setTimeout(() => buildSearchIndex(), 100);
            }

            applyFilters();
        } catch (err) {
            console.error('Failed to load data:', err);
            dom.loading.innerHTML = `
                <div style="color:#f85149;padding:40px;">
                    <p>❌ 数据加载失败</p>
                    <p style="font-size:13px;margin-top:8px;color:#8b949e;">
                        ${err.message}<br>
                        请确认 data/issues.json 文件存在。运行 <code>python scripts/fetch_issues.py</code> 生成数据。
                    </p>
                </div>`;
        }
    }

    function computeSubcatCounts() {
        subcatCounts = {};
        for (const issue of allIssues) {
            const cat = issue.category;
            const sub = issue.subcategory || '其他';
            if (!subcatCounts[cat]) subcatCounts[cat] = {};
            subcatCounts[cat][sub] = (subcatCounts[cat][sub] || 0) + 1;
        }
    }

    // ===== Search Index =====
    function buildSearchIndex() {
        searchIndex = new Map();
        allIssues.forEach((issue, idx) => {
            const text = (issue.title + ' ' + (issue.body || '')).toLowerCase();
            const words = text.match(/[\u4e00-\u9fff]+|[a-z0-9]+/gi) || [];
            words.forEach(word => {
                if (!searchIndex.has(word)) searchIndex.set(word, new Set());
                searchIndex.get(word).add(idx);
            });
        });
        console.log(`Search index built: ${searchIndex.size} terms`);
    }

    function searchIssues(query) {
        if (!query.trim()) return null;
        const q = query.toLowerCase().trim();
        const terms = q.match(/[\u4e00-\u9fff]+|[a-z0-9]+/gi) || [q];

        if (!searchIndex) {
            return allIssues.filter(issue =>
                (issue.title + ' ' + (issue.body || '')).toLowerCase().includes(q)
            );
        }

        let resultSets = terms.map(term => {
            let matches = new Set();
            searchIndex.forEach((indices, key) => {
                if (key.includes(term)) indices.forEach(i => matches.add(i));
            });
            return matches;
        });

        if (resultSets.length === 0) return [];
        let result = resultSets[0];
        for (let i = 1; i < resultSets.length; i++) {
            result = new Set([...result].filter(x => resultSets[i].has(x)));
        }
        return [...result].map(i => allIssues[i]);
    }

    // ===== Filters =====
    function applyFilters() {
        let issues = allIssues;

        // Search filter
        if (searchQuery) {
            const searchResult = searchIssues(searchQuery);
            if (searchResult !== null) issues = searchResult;
        }

        // Category filter
        if (currentCategory !== 'all') {
            issues = issues.filter(i => i.category === currentCategory);
        }

        // Subcategory filter
        if (currentSubcategory !== 'all') {
            issues = issues.filter(i => (i.subcategory || '其他') === currentSubcategory);
        }

        // Month filter
        if (currentMonth !== 'all') {
            issues = issues.filter(i => i.year_month === currentMonth);
        }

        // Sort by newest (default)
        issues.sort((a, b) => b.created_at.localeCompare(a.created_at));

        filteredIssues = issues;
        displayedCount = 0;
        dom.issueList.innerHTML = '';

        if (filteredIssues.length === 0) {
            dom.loading.style.display = 'none';
            dom.emptyState.style.display = 'block';
        } else {
            dom.emptyState.style.display = 'none';
            loadMore();
        }
    }

    function loadMore() {
        if (isLoading || displayedCount >= filteredIssues.length) {
            dom.loading.style.display = 'none';
            return;
        }

        isLoading = true;
        dom.loading.style.display = 'block';

        const fragment = document.createDocumentFragment();
        const end = Math.min(displayedCount + PAGE_SIZE, filteredIssues.length);

        for (let i = displayedCount; i < end; i++) {
            fragment.appendChild(createIssueCard(filteredIssues[i]));
        }

        dom.issueList.appendChild(fragment);
        displayedCount = end;
        isLoading = false;

        if (displayedCount >= filteredIssues.length) {
            dom.loading.style.display = 'none';
        }
    }

    // ===== Card Rendering =====
    function createIssueCard(issue) {
        const card = document.createElement('div');
        card.className = 'issue-card' + (issue.featured ? ' featured' : '');

        const catColors = CATEGORY_COLORS[issue.category] || CATEGORY_COLORS['讨论/反馈'];
        const sub = issue.subcategory || '其他';
        const subMeta = subcatMeta[sub] || { icon: '📌', color: '#8b949e' };
        const bodyText = (issue.body || '').substring(0, 200);
        const hasMoreBody = (issue.body || '').length > 200;

        // Subcategory tag — show only if not '其他'
        const subcatHtml = sub !== '其他'
            ? `<span class="card-subcategory" style="color:${subMeta.color};border-color:${subMeta.color}30;background:${subMeta.color}12">${subMeta.icon} ${sub}</span>`
            : '';

        card.innerHTML = `
            <div class="card-header">
                <span class="card-number">#${issue.number}</span>
                <div class="card-title-area">
                    <div class="card-title">
                        <a href="${issue.html_url}" target="_blank" rel="noopener">${escapeHtml(issue.title)}</a>
                        ${issue.featured ? '<span class="featured-badge">⭐ 已收录</span>' : ''}
                    </div>
                    <div class="card-meta">
                        <span class="card-category" style="background:${catColors.bg};color:${catColors.text}">
                            ${CATEGORY_ICONS[issue.category] || '📌'} ${issue.category}
                        </span>
                        ${subcatHtml}
                        <span class="card-author">
                            <img class="card-avatar" src="${issue.user.avatar_url}&s=36" alt="" loading="lazy" onerror="this.style.display='none'">
                            ${escapeHtml(issue.user.login)}
                        </span>
                        <span class="card-time">${formatRelativeTime(issue.created_at)}</span>
                    </div>
                </div>
            </div>
            ${bodyText ? `
                <div class="card-body ${hasMoreBody ? 'collapsed' : ''}">${escapeHtml(bodyText)}${hasMoreBody ? '…' : ''}</div>
                ${hasMoreBody ? '<button class="expand-btn">展开全文</button>' : ''}
            ` : ''}
            <div class="card-footer">
                <span class="card-stat" title="互动">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    ${issue.reactions}
                </span>
                <span class="card-stat" title="评论">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    ${issue.comments}
                </span>
            </div>
        `;

        // Expand/collapse
        const expandBtn = card.querySelector('.expand-btn');
        if (expandBtn) {
            expandBtn.addEventListener('click', () => {
                const bodyEl = card.querySelector('.card-body');
                if (bodyEl.classList.contains('collapsed')) {
                    bodyEl.classList.remove('collapsed');
                    bodyEl.textContent = issue.body || '';
                    expandBtn.textContent = '收起';
                } else {
                    bodyEl.classList.add('collapsed');
                    bodyEl.textContent = bodyText + '…';
                    expandBtn.textContent = '展开全文';
                }
            });
        }

        return card;
    }

    // ===== UI Builders =====
    function buildCategoryTabs(categoryCounts) {
        const total = allIssues.length;
        dom.countAll.textContent = formatNumber(total);

        const categories = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]);
        categories.forEach(([cat, count]) => {
            const btn = document.createElement('button');
            btn.className = 'cat-btn';
            btn.dataset.category = cat;
            const icon = CATEGORY_ICONS[cat] || '📌';
            btn.innerHTML = `
                <span class="cat-icon">${icon}</span>
                <span class="cat-name">${cat}</span>
                <span class="cat-count">${formatNumber(count)}</span>
            `;
            dom.categoryTabs.appendChild(btn);
        });
    }

    function buildSubcategoryTabs(category) {
        dom.subcatTabs.innerHTML = '';

        if (category === 'all' || !subcatCounts[category]) {
            dom.subfilters.style.display = 'none';
            return;
        }

        const subs = subcatCounts[category];
        const entries = Object.entries(subs).sort((a, b) => b[1] - a[1]);

        // Only show subfilter bar if there's more than 1 subcategory
        if (entries.length <= 1) {
            dom.subfilters.style.display = 'none';
            return;
        }

        dom.subfilters.style.display = 'block';

        // Label
        const label = document.createElement('span');
        label.className = 'subcat-label';
        label.textContent = '细分:';
        dom.subcatTabs.appendChild(label);

        // "全部" button
        const allBtn = document.createElement('button');
        allBtn.className = 'subcat-btn' + (currentSubcategory === 'all' ? ' active' : '');
        allBtn.dataset.subcategory = 'all';
        allBtn.style.cssText = currentSubcategory === 'all'
            ? `background:${CATEGORY_COLORS[category]?.text || '#58a6ff'};color:#fff;`
            : '';
        const totalCount = entries.reduce((s, e) => s + e[1], 0);
        allBtn.innerHTML = `全部 <span class="subcat-count">${formatNumber(totalCount)}</span>`;
        dom.subcatTabs.appendChild(allBtn);

        // Individual subcategory buttons
        entries.forEach(([sub, count]) => {
            const meta = subcatMeta[sub] || { icon: '📌', color: '#8b949e' };
            const btn = document.createElement('button');
            btn.className = 'subcat-btn' + (currentSubcategory === sub ? ' active' : '');
            btn.dataset.subcategory = sub;
            if (currentSubcategory === sub) {
                btn.style.cssText = `background:${meta.color};color:#fff;border-color:${meta.color};`;
            }
            btn.innerHTML = `${meta.icon} ${sub} <span class="subcat-count">${formatNumber(count)}</span>`;
            dom.subcatTabs.appendChild(btn);
        });
    }

    function buildMonthFilter() {
        const months = new Set();
        allIssues.forEach(i => months.add(i.year_month));
        const sorted = [...months].sort().reverse();
        sorted.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            dom.monthFilter.appendChild(opt);
        });
    }

    // ===== Event Handlers =====
    function setupEvents() {
        // Category tabs (level 1)
        dom.categoryTabs.addEventListener('click', (e) => {
            const btn = e.target.closest('.cat-btn');
            if (!btn) return;
            $$('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            currentSubcategory = 'all'; // reset subcategory when category changes
            buildSubcategoryTabs(currentCategory);
            applyFilters();
        });

        // Subcategory tabs (level 2) — delegated
        dom.subcatTabs.addEventListener('click', (e) => {
            const btn = e.target.closest('.subcat-btn');
            if (!btn) return;
            currentSubcategory = btn.dataset.subcategory;
            // Rebuild to update active styles
            buildSubcategoryTabs(currentCategory);
            applyFilters();
        });

        // Month filter
        dom.monthFilter.addEventListener('change', () => {
            currentMonth = dom.monthFilter.value;
            applyFilters();
        });

        // Search
        let searchTimer;
        dom.searchInput.addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                searchQuery = dom.searchInput.value;
                applyFilters();
            }, SEARCH_DEBOUNCE_MS);
        });

        // Keyboard: / to focus search, Esc to clear
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && document.activeElement !== dom.searchInput) {
                e.preventDefault();
                dom.searchInput.focus();
            }
            if (e.key === 'Escape' && document.activeElement === dom.searchInput) {
                dom.searchInput.blur();
                if (searchQuery) {
                    dom.searchInput.value = '';
                    searchQuery = '';
                    applyFilters();
                }
            }
        });

        // Infinite scroll
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && dataLoaded && !isLoading) {
                loadMore();
            }
        }, { rootMargin: '300px' });
        observer.observe(dom.loading);

        // Back to top
        window.addEventListener('scroll', () => {
            dom.backToTop.classList.toggle('visible', window.scrollY > 500);
        }, { passive: true });

        dom.backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        // Reset filters
        dom.resetFilters.addEventListener('click', () => {
            currentCategory = 'all';
            currentSubcategory = 'all';
            currentMonth = 'all';
            searchQuery = '';
            dom.searchInput.value = '';
            dom.monthFilter.value = 'all';
            $$('.cat-btn').forEach(b => b.classList.remove('active'));
            $('.cat-btn[data-category="all"]').classList.add('active');
            dom.subfilters.style.display = 'none';
            applyFilters();
        });
    }

    // ===== Utilities =====
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatNumber(n) {
        if (n >= 10000) return (n / 10000).toFixed(1) + '万';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
        return String(n);
    }

    function formatDate(isoStr) {
        const d = new Date(isoStr);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    function formatRelativeTime(isoStr) {
        const now = Date.now();
        const then = new Date(isoStr).getTime();
        const diff = now - then;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes} 分钟前`;
        if (hours < 24) return `${hours} 小时前`;
        if (days < 30) return `${days} 天前`;
        if (days < 365) return `${Math.floor(days / 30)} 个月前`;
        return formatDate(isoStr);
    }

    // ===== Init =====
    setupEvents();
    loadData();

})();
