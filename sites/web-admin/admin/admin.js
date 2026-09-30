/**
 * StarClub 管理后台脚本 v0.9
 * 支持动态加载和保存网站数据，包含完整的增删改查功能
 */

// 当前数据缓存
let currentData = null;

// 最近更新记录存储键名
const RECENT_UPDATES_KEY = 'starclub_recent_updates';
const MAX_RECENT_ITEMS = 10;

// 常用 Emoji 分类数据
const commonEmojis = {
    '常用': ['🔐', '🔒', '📚', '🎮', '🤝', '🎯', '🚀', '💡', '⭐', '✨', '🔥', '💎', '🛡️', '🔑', '📱', '💻', '🌐', '⚡', '📊', '📈'],
    '安全': ['🔐', '🔒', '🔓', '🛡️', '🔑', '🔏', '🔎', '🕵️', '🚨', '⚠️', '🔰', '📛', '🔴', '🟢', '🔵'],
    '学习': ['📚', '📖', '✏️', '📝', '🎓', '📌', '📍', '🔖', '🏷️', '📎', '✂️', '📐', '📏', '🧮', '🔬'],
    '共创': ['🎮', '🎯', '🏆', '🎪', '🎨', '🎭', '🎬', '🎤', '🎧', '🎸', '🎹', '🎲', '🎰', '🎳', '🎯'],
    '团队': ['🤝', '👥', '👤', '👨‍👩‍👧‍👦', '🧑‍🤝‍🧑', '👫', '👬', '👭', '🏃', '💪', '🙌', '👏', '🤲', '🤜', '🤛'],
    '科技': ['💻', '🖥️', '💾', '💿', '📀', '📱', '☎️', '📞', '📟', '📠', '📡', '📺', '📻', '🎙️', '🔋'],
    '其他': ['✅', '❌', '⭕', '❓', '❗', '‼️', '⁉️', '➕', '➖', '➗', '✖️', '💯', '💢', '♨️', '🚩']
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    await loadCurrentData();
    updateRecentUpdates();
    setupNavigation();
    setupFormListeners();
    setupBottomActions();
    updateDashboardStats();
    renderAllTables();
    initEmojiPickers();
    // 延迟初始化拖拽排序，等表格渲染完成
    setTimeout(initSortableTables, 100);
});

// ============ 拖拽排序 ============

let sortableInstances = {}; // 存储 Sortable 实例

function initSortableTables() {
    // 初始化各表格的拖拽排序
    initSortable('quickLinksTableBody', 'quickLinks', updateQuickLinksOrder);
    initSortable('coreActivitiesTableBody', 'coreActivities', updateCoreActivitiesOrder);
    initSortable('activitiesTableBody', 'activities', updateActivitiesOrder);
    initSortable('membersTableBody', 'members', updateMembersOrder);
    initSortable('organizationTableBody', 'organization', updateOrgOrder);
    // 资源表格需要特殊处理（按分类）
    initSortable('resourcesTableBody', 'resources', updateResourcesOrder, true);
}

function initSortable(tableId, field, onUpdateCallback, isResourceTable = false) {
    const tableBody = document.getElementById(tableId);
    if (!tableBody) return;

    // 如果已有实例，先销毁
    if (sortableInstances[tableId]) {
        sortableInstances[tableId].destroy();
    }

    const sortable = new Sortable(tableBody, {
        animation: 200,
        handle: '.sort-handle',
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        filter: '.category-header', // 分类标题行不可拖拽
        preventOnFilter: true,
        onEnd: function(evt) {
            if (evt.oldIndex !== evt.newIndex) {
                if (isResourceTable) {
                    handleResourceSort(evt, field, onUpdateCallback);
                } else {
                    handleSort(evt, field, onUpdateCallback);
                }
            }
        }
    });

    sortableInstances[tableId] = sortable;
}

function handleSort(evt, field, onUpdateCallback) {
    const tableBody = evt.to;
    const rows = Array.from(tableBody.querySelectorAll('tr:not(.category-header)'));
    const orderedIds = [];

    rows.forEach(row => {
        const index = parseInt(row.dataset.index);
        if (!isNaN(index)) {
            orderedIds.push(index);
        }
    });

    if (orderedIds.length > 0) {
        onUpdateCallback(orderedIds);
    }
}

function handleResourceSort(evt, field, onUpdateCallback) {
    const tableBody = evt.to;
    const rows = Array.from(tableBody.querySelectorAll('tr:not(.category-header)'));

    // 对于资源表，我们需要收集所有数据的原始索引
    // 因为资源是按分类显示的，所以排序会影响整个列表
    const allRows = Array.from(tableBody.querySelectorAll('tr'));
    const orderedIds = [];

    allRows.forEach(row => {
        if (!row.classList.contains('category-header')) {
            const index = parseInt(row.dataset.index);
            if (!isNaN(index)) {
                orderedIds.push(index);
            }
        }
    });

    if (orderedIds.length > 0) {
        onUpdateCallback(orderedIds);
    }
}

async function updateQuickLinksOrder(orderedIds) {
    await saveSortOrder('quickLinks', orderedIds);
}

async function updateCoreActivitiesOrder(orderedIds) {
    await saveSortOrder('coreActivities', orderedIds);
}

async function updateMembersOrder(orderedIds) {
    await saveSortOrder('members', orderedIds);
}

async function updateOrgOrder(orderedIds) {
    await saveSortOrder('organization', orderedIds);
}

async function updateActivitiesOrder(orderedIds) {
    await saveSortOrder('activities', orderedIds);
}

async function updateResourcesOrder(orderedIds) {
    await saveSortOrder('resources', orderedIds);
}

async function saveSortOrder(field, orderedIds) {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'sort_items',
                field: field,
                orderedIds: orderedIds
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('排序已更新', 'success');
            await loadCurrentData();
            renderAllTables();
            // 重新初始化拖拽
            setTimeout(initSortableTables, 100);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('排序保存失败: ' + error.message, 'error');
        await loadCurrentData();
        renderAllTables();
        setTimeout(initSortableTables, 100);
    }
}

// ============ Emoji 选择器 ============

function initEmojiPickers() {
    // 为所有 emoji 选择器填充内容
    document.querySelectorAll('.emoji-picker-dropdown').forEach(picker => {
        picker.innerHTML = generateEmojiPickerHtml();
    });

    // 点击外部关闭选择器
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.emoji-picker-wrapper')) {
            document.querySelectorAll('.emoji-picker-dropdown').forEach(p => p.classList.remove('show'));
        }
    });
}

function generateEmojiPickerHtml() {
    let html = '';
    for (const [category, emojis] of Object.entries(commonEmojis)) {
        html += `
            <div class="emoji-category">
                <div class="emoji-category-title">${category}</div>
                <div class="emoji-grid">
                    ${emojis.map(emoji => `<button type="button" class="emoji-option" onclick="selectEmoji('${emoji}', this)">${emoji}</button>`).join('')}
                </div>
            </div>
        `;
    }
    return html;
}

function toggleEmojiPicker(pickerId) {
    const picker = document.getElementById(pickerId);
    if (picker) {
        const isShowing = picker.classList.contains('show');
        // 关闭所有其他选择器
        document.querySelectorAll('.emoji-picker-dropdown').forEach(p => p.classList.remove('show'));
        // 切换当前选择器
        if (!isShowing) {
            picker.classList.add('show');
        }
    }
}

function selectEmoji(emoji, btn) {
    const picker = btn.closest('.emoji-picker-dropdown');
    const wrapper = btn.closest('.emoji-picker-wrapper');
    const input = wrapper.querySelector('.emoji-input');
    if (input) {
        input.value = emoji;
        // 触发 change 事件以标记字段已修改
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    picker.classList.remove('show');
}

// ============ 数据加载与保存 ============

/**
 * 将 input[type="date"] 的 YYYY-MM-DD 格式转换为中文格式保存
 */
function formatDateForSave(dateStr) {
    if (!dateStr) return '';
    // YYYY-MM-DD 格式转换为中文格式
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        const [year, month, day] = dateStr.split('-');
        return `${year}年${parseInt(month)}月${parseInt(day)}日`;
    }
    // 其他格式直接返回原值
    return dateStr;
}

/**
 * 将 input[type="month"] 的 YYYY-MM 格式转换为中文年月格式保存
 */
function formatMonthForSave(monthStr) {
    if (!monthStr) return '';
    // YYYY-MM 格式转换为中文年月格式
    if (/^\d{4}-\d{2}$/.test(monthStr)) {
        const [year, month] = monthStr.split('-');
        return `${year}年${parseInt(month)}月`;
    }
    // 其他格式直接返回原值
    return monthStr;
}

/**
 * 格式化日期为中文显示格式（YYYY年MM月DD日）
 */
function formatDateForDisplay(dateStr) {
    if (!dateStr) return '';
    // 已经是中文格式
    if (/^\d{4}年\d{1,2}月\d{1,2}日$/.test(dateStr)) {
        return dateStr;
    }
    // 已经是 YYYY-MM-DD 格式
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        const [year, month, day] = dateStr.split('-');
        return `${year}年${month}月${day}日`;
    }
    // 其他格式直接返回原值
    return dateStr;
}

/**
 * 获取当前日期（YYYY-MM-DD 格式）
 */
function getCurrentDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * 获取当前年月（YYYY-MM 格式）
 */
function getCurrentMonth() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
}

/**
 * 解析日期为 input[type="date"] 所需的 YYYY-MM-DD 格式
 */
function parseDateForInput(dateStr) {
    if (!dateStr) return '';
    // 已经是 YYYY-MM-DD 格式
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
    }
    // 中文格式 YYYY年MM月DD日
    const cnMatch = dateStr.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日$/);
    if (cnMatch) {
        return `${cnMatch[1]}-${cnMatch[2].padStart(2, '0')}-${cnMatch[3].padStart(2, '0')}`;
    }
    // YYYY/MM/DD 格式
    const slashMatch = dateStr.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
    if (slashMatch) {
        return `${slashMatch[1]}-${slashMatch[2].padStart(2, '0')}-${slashMatch[3].padStart(2, '0')}`;
    }
    // 尝试直接转换
    return dateStr;
}

/**
 * 解析成果日期为 input[type="month"] 所需的 YYYY-MM 格式
 */
function parseAchievementDateForInput(dateStr) {
    if (!dateStr) return '';
    // 已经是 YYYY-MM 格式
    if (/^\d{4}-\d{2}$/.test(dateStr)) {
        return dateStr;
    }
    // 中文格式 YYYY年MM月
    const cnMatch = dateStr.match(/^(\d{4})年(\d{1,2})月$/);
    if (cnMatch) {
        return `${cnMatch[1]}-${cnMatch[2].padStart(2, '0')}`;
    }
    // YYYY年MM月DD日 格式，取年月部分
    const fullDateMatch = dateStr.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日$/);
    if (fullDateMatch) {
        return `${fullDateMatch[1]}-${fullDateMatch[2].padStart(2, '0')}`;
    }
    return '';
}

/**
 * 从服务器加载当前数据
 * @param {boolean} showToastOnSuccess - 是否在成功时显示 toast，默认 false
 */
async function loadCurrentData(showToastOnSuccess = false) {
    try {
        const response = await fetch('/api/data');
        if (!response.ok) {
            throw new Error('加载数据失败');
        }
        const result = await response.json();

        if (result.success && result.data) {
            currentData = result.data;
            populateForms(currentData);
            if (showToastOnSuccess) {
                showToast('数据加载成功', 'success');
            }
        } else {
            throw new Error(result.error || '数据加载失败');
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        showToast('加载失败: ' + error.message, 'error');
    }
}

/**
 * 填充表单数据
 */
function populateForms(data) {
    // Hero 区域
    if (data.hero) {
        setFormValue('heroTitle', data.hero.title);
        setFormValue('heroSubtitle', data.hero.subtitle);
        setFormValue('heroDesc', data.hero.desc);
        setFormValue('heroBtn1Text', data.hero.btn1Text);
        setFormValue('heroBtn1Link', data.hero.btn1Link);
        setFormValue('heroBtn2Text', data.hero.btn2Text);
        setFormValue('heroBtn2Link', data.hero.btn2Link);
    }

    // 统计数据
    if (data.stats) {
        setFormValue('foundedYear', data.stats.foundedYear);
        setFormValue('memberCount', data.stats.memberCount);
        setFormValue('activityCount', data.stats.activityCount);
        setFormValue('foundedYearLabel', data.stats.foundedYearLabel);
        setFormValue('memberCountLabel', data.stats.memberCountLabel);
        setFormValue('activityCountLabel', data.stats.activityCountLabel);
    }

    // 核心共创 - 前4条
    if (data.coreActivities && data.coreActivities.length > 0) {
        for (let i = 0; i < 4; i++) {
            if (data.coreActivities[i]) {
                setFormValue(`activityIcon${i+1}`, data.coreActivities[i].icon);
                setFormValue(`activityTitle${i+1}`, data.coreActivities[i].title);
                setFormValue(`activityDesc${i+1}`, data.coreActivities[i].desc);
                setFormValue(`activityLink${i+1}`, data.coreActivities[i].link || '');
            }
        }
    }

    // 关于我们
    if (data.about) {
        setFormValue('aboutTitle', data.about.title);
        setFormValue('aboutSubtitle', data.about.subtitle);
        setFormValue('aboutContent', data.about.content);
        setFormValue('aboutVision', data.about.vision);

        // 星社宗旨
        if (data.about.values && data.about.values.length > 0) {
            for (let i = 0; i < 3; i++) {
                if (data.about.values[i]) {
                    setFormValue(`valueIcon${i+1}`, data.about.values[i].icon);
                    setFormValue(`valueTitle${i+1}`, data.about.values[i].title);
                    setFormValue(`valueDesc${i+1}`, data.about.values[i].desc);
                }
            }
        }
    }

    // 指导老师
    if (data.advisor) {
        setFormValue('advisorName', data.advisor.name || '');
        setFormValue('advisorTitle', data.advisor.title || '指导老师');
        setFormValue('advisorTitleFull', data.advisor.titleFull || '');
        setFormValue('advisorPhoto', data.advisor.photo || '');
        setFormValue('advisorBio', data.advisor.bio || '');
        setFormValue('advisorLink', data.advisor.link || '');
        if (data.advisor.researchAreas && data.advisor.researchAreas.length > 0) {
            setFormValue('advisorResearchAreas', data.advisor.researchAreas.join('\n'));
        }
    }

    // 星社机制介绍
    setFormValue('orgIntroInput', data.organizationIntro || '');

    // 联系方式
    if (data.contact) {
        setFormValue('contactQqGroup', data.contact.qqGroup);
        setFormValue('contactWechat', data.contact.wechat);
        setFormValue('contactEmail', data.contact.email);
        setFormValue('contactLocation', data.contact.location);
        setFormValue('contactGithub', data.contact.github);
    }

    // 招募信息
    if (data.join) {
        setFormValue('joinQqGroup', data.join.qqGroup);
        setFormValue('joinStatus', data.join.status || 'open');
        setFormValue('joinNotice', data.join.notice);
        setFormValue('joinRequirements', (data.join.requirements || []).join('\n'));
        setFormValue('joinBenefits', (data.join.benefits || []).join('\n'));
        setFormValue('joinTime', data.join.time);
        setFormValue('joinLocation', data.join.location);
        setFormValue('joinLink', data.join.link);
        // 渲染FAQ
        renderFaqItems(data.join.faq || []);
    }

    // 页脚信息
    if (data.footer) {
        setFormValue('footerCopyright', data.footer.copyright);
        setFormValue('footerIcp', data.footer.icp);
        setFormValue('footerGithub', data.footer.github);
        setFormValue('column1Title', data.footer.column1Title);
        setFormValue('column2Title', data.footer.column2Title);
        setFormValue('column3Title', data.footer.column3Title);

        // 渲染页脚子项
        renderFooterItems('column1', data.footer.column1Items || []);
        renderFooterItems('column2', data.footer.column2Items || []);
        renderFooterItems('column3', data.footer.column3Items || []);
    }
}

/**
 * 渲染页脚子项
 */
function renderFooterItems(column, items) {
    const container = document.getElementById(column + 'Items');
    if (!container) return;

    container.innerHTML = items.map((item, index) => createFooterItemHtml(column, index, item)).join('');
}

/**
 * 创建页脚子项HTML - 两行布局设计
 */
function createFooterItemHtml(column, index, item = {}) {
    const uniqueId = column + '_' + index;

    return `
        <div class="footer-item-row" data-column="${column}" data-index="${index}">
            <div class="footer-item-fields" style="padding: 12px; background: #f9f9f9; border-radius: 8px; margin-bottom: 10px; border: 1px solid #eee;">
                <div style="margin-bottom: 10px;">
                    <label style="font-size: 12px; color: #666; margin-bottom: 4px; display: block;">链接文字</label>
                    <input type="text" class="footer-item-text" value="${escapeHtml(item.text || '')}" placeholder="输入链接显示文字" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;">
                </div>
                <div style="margin-bottom: 10px;">
                    <label style="font-size: 12px; color: #666; margin-bottom: 4px; display: block;">链接地址</label>
                    <input type="text" class="footer-item-link" value="${escapeHtml(item.link || '')}" placeholder="如：about.html 或 https://..." style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;">
                </div>
                <div style="text-align: right;">
                    <button type="button" class="btn-tiny btn-delete" onclick="removeFooterItem('${column}', ${index})">删除</button>
                </div>
            </div>
        </div>
    `;
}

/**
 * 添加页脚子项
 */
function addFooterItem(column) {
    const container = document.getElementById(column + 'Items');
    const items = container.querySelectorAll('.footer-item-row');
    const newIndex = items.length;

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = createFooterItemHtml(column, newIndex);
    container.appendChild(tempDiv.firstElementChild);
}

/**
 * 删除页脚子项
 */
function removeFooterItem(column, index) {
    const container = document.getElementById(column + 'Items');
    const item = container.querySelector(`[data-column="${column}"][data-index="${index}"]`);
    if (item) {
        item.remove();
        // 重新索引
        reindexFooterItems(column);
    }
}

/**
 * 重新索引页脚子项
 */
function reindexFooterItems(column) {
    const container = document.getElementById(column + 'Items');
    const items = container.querySelectorAll('.footer-item-row');
    items.forEach((item, newIndex) => {
        item.dataset.index = newIndex;
        const textInput = item.querySelector('.footer-item-text');
        const linkInput = item.querySelector('.footer-item-link');
        const deleteBtn = item.querySelector('.btn-delete');

        if (textInput) textInput.name = `footer_${column}_text_${newIndex}`;
        if (linkInput) linkInput.name = `footer_${column}_link_${newIndex}`;
        if (deleteBtn) deleteBtn.setAttribute('onclick', `removeFooterItem('${column}', ${newIndex})`);
    });
}

/**
 * 渲染FAQ列表
 */
function renderFaqItems(faqList) {
    const container = document.getElementById('faqContainer');
    if (!container) return;

    if (faqList.length === 0) {
        container.innerHTML = '<p style="color: #888; font-size: 13px;">暂无常见问题，点击添加</p>';
        return;
    }

    container.innerHTML = faqList.map((faq, index) => createFaqItemHtml(index, faq)).join('');
}

/**
 * 创建FAQ项HTML
 */
function createFaqItemHtml(index, faq = {}) {
    return `
        <div class="faq-item-row" data-index="${index}" style="padding: 12px; background: #f9f9f9; border-radius: 8px; margin-bottom: 10px; border: 1px solid #eee;">
            <div style="margin-bottom: 10px;">
                <label style="font-size: 12px; color: #666; margin-bottom: 4px; display: block;">问题</label>
                <input type="text" class="faq-question" value="${escapeHtml(faq.question || '')}" placeholder="请输入问题" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;">
            </div>
            <div style="margin-bottom: 10px;">
                <label style="font-size: 12px; color: #666; margin-bottom: 4px; display: block;">回答</label>
                <textarea class="faq-answer" rows="3" placeholder="请输入回答" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; resize: vertical;">${escapeHtml(faq.answer || '')}</textarea>
            </div>
            <div style="text-align: right;">
                <button type="button" class="btn-tiny btn-delete" onclick="removeFaqItem(${index})">删除</button>
            </div>
        </div>
    `;
}

/**
 * 添加FAQ项
 */
function addFaqItem() {
    const container = document.getElementById('faqContainer');
    if (!container) return;

    // 如果当前显示的是"暂无"提示，清空它
    if (container.querySelector('p')) {
        container.innerHTML = '';
    }

    const items = container.querySelectorAll('.faq-item-row');
    const newIndex = items.length;

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = createFaqItemHtml(newIndex);
    container.appendChild(tempDiv.firstElementChild);
}

/**
 * 删除FAQ项
 */
function removeFaqItem(index) {
    const container = document.getElementById('faqContainer');
    const item = container.querySelector(`[data-index="${index}"]`);
    if (item) {
        item.remove();
        // 重新索引
        reindexFaqItems();
    }
}

/**
 * 重新索引FAQ项
 */
function reindexFaqItems() {
    const container = document.getElementById('faqContainer');
    const items = container.querySelectorAll('.faq-item-row');
    items.forEach((item, newIndex) => {
        item.dataset.index = newIndex;
        const deleteBtn = item.querySelector('.btn-delete');
        if (deleteBtn) {
            deleteBtn.setAttribute('onclick', `removeFaqItem(${newIndex})`);
        }
    });
}

/**
 * 收集FAQ数据
 */
function collectFaqItems() {
    const container = document.getElementById('faqContainer');
    if (!container) return [];

    const items = [];
    container.querySelectorAll('.faq-item-row').forEach(row => {
        const question = row.querySelector('.faq-question')?.value?.trim() || '';
        const answer = row.querySelector('.faq-answer')?.value?.trim() || '';

        if (question || answer) {
            items.push({ question, answer });
        }
    });

    return items;
}

/**
 * 收集页脚子项数据
 */
function collectFooterItems() {
    const columns = ['column1', 'column2', 'column3'];
    const result = {};

    columns.forEach(column => {
        const container = document.getElementById(column + 'Items');
        if (!container) return;

        const items = [];
        container.querySelectorAll('.footer-item-row').forEach(row => {
            const text = row.querySelector('.footer-item-text')?.value || '';
            const link = row.querySelector('.footer-item-link')?.value || '';

            if (text || link) {
                items.push({ text, link });
            }
        });

        const columnKey = column.replace('column', 'column') + 'Items';
        result[columnKey] = items;
    });

    return result;
}

/**
 * 设置表单字段值
 */
function setFormValue(fieldId, value) {
    const field = document.getElementById(fieldId);
    if (field && value !== undefined && value !== null) {
        field.value = value;
    }
}

// ============ 导航与界面 ============

/**
 * 设置导航切换
 */
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-section]');
    const sections = document.querySelectorAll('.section');
    const pageTitle = document.getElementById('pageTitle');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.dataset.section;

            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(section => {
                section.classList.toggle('active', section.id === sectionId);
            });

            if (pageTitle && item.querySelector('span:last-child')) {
                pageTitle.textContent = item.querySelector('span:last-child').textContent;
            }
        });
    });
}

/**
 * 设置表单监听器
 */
function setupFormListeners() {
    const forms = document.querySelectorAll('.section form');
    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });

    document.querySelectorAll('input, textarea, select').forEach(field => {
        field.addEventListener('input', () => markFieldAsChanged(field));
    });
}

/**
 * 设置底部操作栏
 */
function setupBottomActions() {
    const previewBtn = document.querySelector('.btn-preview');
    const saveAllBtn = document.querySelector('.btn-save-all');

    if (previewBtn) {
        previewBtn.addEventListener('click', previewChanges);
    }
    if (saveAllBtn) {
        saveAllBtn.addEventListener('click', saveAllChanges);
    }
}

/**
 * 更新仪表盘统计
 */
function updateDashboardStats() {
    if (!currentData) return;

    const setCount = (id, data) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = data ? (Array.isArray(data) ? data.length : Object.keys(data).length) : 0;
        }
    };

    // 共创管理中，统计 visible=true 的数量（用于首页最新动态）
    const visibleActivities = currentData.activities
        ? currentData.activities.filter(a => a.visible !== false).length
        : 0;

    // 将 newsCount 改成显示 visible=true 的共创数
    const newsCountEl = document.getElementById('newsCount');
    if (newsCountEl) newsCountEl.textContent = visibleActivities;

    setCount('activitiesCount', currentData.activities);
    setCount('membersCount', currentData.members);
    setCount('resourcesCount', currentData.resources);
}

// ============ 最近更新 ============

function getRecentUpdates() {
    try {
        const data = localStorage.getItem(RECENT_UPDATES_KEY);
        return data ? JSON.parse(data) : [];
    } catch {
        return [];
    }
}

function saveRecentUpdate(module, action, title) {
    const updates = getRecentUpdates();
    const newUpdate = {
        module,
        action,
        title,
        time: new Date().toISOString()
    };
    updates.unshift(newUpdate);
    if (updates.length > MAX_RECENT_ITEMS) {
        updates.pop();
    }
    localStorage.setItem(RECENT_UPDATES_KEY, JSON.stringify(updates));
    return updates;
}

function updateRecentUpdates() {
    const container = document.getElementById('recentUpdates');
    if (!container) return;

    const updates = getRecentUpdates();

    if (updates.length === 0) {
        container.innerHTML = '<p class="no-data">暂无更新记录</p>';
        return;
    }

    const moduleNames = {
        'quickLinks': '快速入口',
        'coreActivities': '核心共创',
        'activities': '共创风采',
        'members': '成员风采',
        'achievements': '成果展示',
        'resources': '学习资源',
        'books': '推荐书籍',
        'organization': '星社机制',
        'footerItems': '页脚信息',
        'detailPages': '详情页',
        'faq': 'FAQ'
    };

    const actionNames = {
        'add': '添加',
        'edit': '编辑',
        'delete': '删除'
    };

    container.innerHTML = updates.map(item => {
        const time = new Date(item.time);
        const timeStr = time.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        return `
            <div class="recent-item" style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="color:var(--primary-color);font-weight:500;">${moduleNames[item.module] || item.module}</span>
                    <span style="color:#666;">${actionNames[item.action] || item.action}</span>
                    <span style="color:var(--text-dark);font-weight:500;">${escapeHtml(item.title)}</span>
                </div>
                <span style="color:#999;font-size:11px;">${timeStr}</span>
            </div>
        `;
    }).join('');
}

function recordUpdate(module, action, title) {
    saveRecentUpdate(module, action, title);
    updateRecentUpdates();
    fetch('/api/operation-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module, action, title })
    }).catch(err => console.warn('服务端日志记录失败:', err));
}

// ============ 渲染表格 ============

/**
 * 渲染所有表格
 */
function renderAllTables() {
    renderQuickLinksTable();
    renderCoreActivitiesTable();
    renderActivitiesTable();
    renderMembersTable();
    renderAchievementsTable();
    renderResourcesTable();
    renderBooksTable();
    renderOrganizationTable();
    initOrgIntro();
    loadDetailPages();
    loadAccountsTable();
}

/**
 * 渲染快速入口表格
 */
function renderQuickLinksTable() {
    const tbody = document.getElementById('quickLinksTableBody');
    if (!tbody || !currentData) return;

    const links = currentData.quickLinks || [];
    if (links.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无快速入口数据</td></tr>';
        return;
    }

    tbody.innerHTML = links.map((item, index) => `
        <tr data-index="${index}">
            <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
            <td style="text-align:center; font-size:24px;">${escapeHtml(item.icon || '📎')}</td>
            <td>${escapeHtml(item.title || '')}</td>
            <td>${escapeHtml(item.desc || '')}</td>
            <td>${item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" style="color:#005a8c;">${escapeHtml(item.link)}</a>` : '-'}</td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editQuickLink(${index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteQuickLink(${index})">删除</button>
            </td>
        </tr>
    `).join('');
}

/**
 * 渲染核心共创表格
 */
function renderCoreActivitiesTable() {
    const tbody = document.getElementById('coreActivitiesTableBody');
    if (!tbody || !currentData) return;

    const activities = currentData.coreActivities || [];
    if (activities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无核心共创数据</td></tr>';
        return;
    }

    tbody.innerHTML = activities.map((item, index) => `
        <tr data-index="${index}">
            <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
            <td style="text-align:center; font-size:24px;">${escapeHtml(item.icon || '📌')}</td>
            <td>${escapeHtml(item.title || '')}</td>
            <td>${escapeHtml(item.desc || '')}</td>
            <td>${item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" style="color:#005a8c;">${escapeHtml(item.link)}</a>` : '-'}</td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editCoreActivity(${index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteCoreActivity(${index})">删除</button>
            </td>
        </tr>
    `).join('');
}

/**
 * 渲染共创表格
 */
function renderActivitiesTable() {
    const tbody = document.getElementById('activitiesTableBody');
    if (!tbody || !currentData) return;

    let activities = [...(currentData.activities || [])];
    if (activities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无共创数据</td></tr>';
        return;
    }

    // 记录原始索引，然后按日期倒序排列（最新的在前）
    activities.forEach((item, index) => { item._index = index; });
    activities.sort((a, b) => {
        const dateA = parseDateForInput(a.date);
        const dateB = parseDateForInput(b.date);
        return dateB.localeCompare(dateA);
    });

    tbody.innerHTML = activities.map((item) => `
        <tr data-index="${item._index}">
            <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
            <td>${formatDateForDisplay(item.date)}</td>
            <td>${escapeHtml(item.title || '')}</td>
            <td>${escapeHtml(item.desc || '')}</td>
            <td>${item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" style="color:#005a8c;">链接</a>` : '-'}</td>
            <td style="text-align:center;">
                <label class="switch">
                    <input type="checkbox" ${item.visible !== false ? 'checked' : ''} onchange="toggleActivityVisible(${item._index})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editActivity(${item._index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteActivity(${item._index})">删除</button>
            </td>
        </tr>
    `).join('');
}

/**
 * 渲染成员表格
 */
function renderMembersTable() {
    const tbody = document.getElementById('membersTableBody');
    if (!tbody || !currentData) return;

    const members = currentData.members || [];
    if (members.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#999;">暂无成员数据</td></tr>';
        return;
    }

    const html = members.map((item, index) => {
        // 判断 photo 是否为图片（URL 或图片路径）
        let photo = item.photo || '';
        // 处理相对路径：在 admin 页面中，uploads 路径需要加上 ../
        if (photo && !photo.startsWith('http') && !photo.startsWith('/')) {
            photo = '../' + photo;
        }
        const isImage = /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(photo) || photo.startsWith('http');
        const avatarHtml = isImage
            ? `<img src="${escapeHtml(photo)}" alt="${escapeHtml(item.name || '')}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:8px;" onerror="this.style.display='none';this.nextElementSibling.style.display='inline-block';"><span style="display:none;width:40px;height:40px;border-radius:50%;background:#e0e0e0;text-align:center;line-height:40px;margin-right:8px;vertical-align:middle;">👤</span>`
            : (item.photo ? `<span style="display:inline-block;width:40px;height:40px;border-radius:50%;background:#e0e0e0;text-align:center;line-height:40px;margin-right:8px;vertical-align:middle;font-size:18px;">${escapeHtml(item.photo)}</span>` : `<span style="display:inline-block;width:40px;height:40px;border-radius:50%;background:#e0e0e0;text-align:center;line-height:40px;margin-right:8px;vertical-align:middle;">👤</span>`);

        return `<tr data-index="${index}">
            <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
            <td>${avatarHtml}${escapeHtml(item.name || '')}</td>
            <td>${escapeHtml(item.grade || '')}</td>
            <td>${escapeHtml(item.field || '')}</td>
            <td>${escapeHtml(item.bio || '')}</td>
            <td>${item.link ? '<a href="' + escapeHtml(item.link) + '" target="_blank" style="color:#005a8c;">查看</a>' : '-'}</td>
            <td style="text-align:center;">
                <label class="switch">
                    <input type="checkbox" ${item.visible !== false ? 'checked' : ''} onchange="toggleMemberVisible(${index})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editMember(${index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteMember(${index})">删除</button>
            </td>
        </tr>`;
    }).join('');
    tbody.innerHTML = html;
}

/**
 * 渲染星社成就表格
 */
function renderAchievementsTable() {
    const tbody = document.getElementById('achievementsTableBody');
    if (!tbody || !currentData) return;

    let achievements = [...(currentData.achievements || [])];
    if (achievements.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无成果数据</td></tr>';
        return;
    }

    // 记录原始索引，然后按年月倒序排列（最新的在前）
    achievements.forEach((item, index) => { item._index = index; });
    achievements.sort((a, b) => {
        const dateA = parseAchievementDateForInput(a.date) || '';
        const dateB = parseAchievementDateForInput(b.date) || '';
        return dateB.localeCompare(dateA);
    });

    tbody.innerHTML = achievements.map((item) => {
        // 成果日期显示为年月格式
        let dateDisplay = '';
        if (item.date) {
            const match = item.date.match(/^(\d{4})年(\d{1,2})月$/);
            if (match) {
                dateDisplay = `${match[1]}年${match[2]}月`;
            } else {
                dateDisplay = item.date;
            }
        }

        return `<tr>
            <td>${escapeHtml(dateDisplay)}</td>
            <td><strong>${escapeHtml(item.title || '')}</strong></td>
            <td>${escapeHtml(item.desc || '')}</td>
            <td>${item.link ? '<a href="' + escapeHtml(item.link) + '" target="_blank" style="color:#005a8c;">查看</a>' : '-'}</td>
            <td style="text-align:center;">
                <label class="switch">
                    <input type="checkbox" ${item.visible !== false ? 'checked' : ''} onchange="toggleAchievementVisible(${item._index})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editAchievement(${item._index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteAchievement(${item._index})">删除</button>
            </td>
        </tr>`;
    }).join('');
}

/**
 * 渲染资源表格（按类别分组）
 */
function renderResourcesTable() {
    const tbody = document.getElementById('resourcesTableBody');
    if (!tbody || !currentData) return;

    const resources = currentData.resources || [];
    if (resources.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无资源数据</td></tr>';
        return;
    }

    // 按类别分组
    const categories = {};
    resources.forEach((item, index) => {
        const cat = item.category || '其他';
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push({ ...item, _index: index });
    });

    let html = '';
    for (const [category, items] of Object.entries(categories)) {
        html += `<tr class="category-header"><td colspan="6" style="background:#e8f4fc;font-weight:bold;">📂 ${escapeHtml(category)}</td></tr>`;
        items.forEach(item => {
            html += `
                <tr data-index="${item._index}">
                    <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
                    <td style="text-align:center;font-size:20px;">${escapeHtml(item.icon || '📚')}</td>
                    <td>${escapeHtml(item.title || '')}</td>
                    <td>${escapeHtml(item.desc || '')}</td>
                    <td style="text-align:center;">
                        <label class="switch">
                            <input type="checkbox" ${item.visible !== false ? 'checked' : ''} onchange="toggleResourceVisible(${item._index})">
                            <span class="slider"></span>
                        </label>
                    </td>
                    <td>
                        <button class="btn-tiny btn-edit" onclick="editResource(${item._index})">编辑</button>
                        <button class="btn-tiny btn-delete" onclick="deleteResource(${item._index})">删除</button>
                    </td>
                </tr>
            `;
        });
    }
    tbody.innerHTML = html;
}

/**
 * 渲染星社机制表格
 */
// 初始化星社机制介绍
function initOrgIntro() {
    const input = document.getElementById('orgIntroInput');
    if (input && currentData && currentData.organizationIntro) {
        input.value = currentData.organizationIntro;
    }
}

// 保存星社机制介绍
async function saveOrgIntro() {
    const input = document.getElementById('orgIntroInput');
    const value = input.value.trim();

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_text',
                field: 'organizationIntro',
                value: value
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('星社机制介绍已保存', 'success');
            await loadCurrentData();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

function renderOrganizationTable() {
    const tbody = document.getElementById('organizationTableBody');
    if (!tbody || !currentData) return;

    const org = currentData.organization || [];
    if (org.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">暂无星社机制数据</td></tr>';
        return;
    }

    tbody.innerHTML = org.map((item, index) => `
        <tr data-index="${index}">
            <td style="text-align:center; cursor:move;" class="sort-handle" title="拖动排序">☰</td>
            <td style="text-align:center;font-size:20px;">${escapeHtml(item.icon || '📌')}</td>
            <td><strong>${escapeHtml(item.name || '')}</strong></td>
            <td>${escapeHtml(item.description || '')}</td>
            <td style="text-align:center;">
                <label class="switch" style="margin:0; display:inline-block;">
                    <input type="checkbox" ${item.visible !== false ? 'checked' : ''} onchange="toggleOrgVisible(${index})">
                    <span class="slider"></span>
                </label>
            </td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editOrg(${index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteOrg(${index})">删除</button>
            </td>
        </tr>
    `).join('');
}

// ============ 共创管理 ============

let editingActivityIndex = -1;

async function toggleActivityVisible(index) {
    if (!currentData.activities[index]) return;
    currentData.activities[index].visible = !currentData.activities[index].visible;

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_item',
                field: 'activities',
                index: index,
                item: currentData.activities[index]
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('更新成功', 'success');
        } else {
            // 回滚
            currentData.activities[index].visible = !currentData.activities[index].visible;
            renderActivitiesTable();
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    }
}

function showAddModal(type) {
    if (type === 'activities') {
        editingActivityIndex = -1;
        document.getElementById('modalTitle').textContent = '添加共创';
        document.getElementById('modalBody').innerHTML = `
            <div class="form-group">
                <label for="modalDate">日期</label>
                <input type="date" id="modalDate" value="${getCurrentDate()}" required>
            </div>
            <div class="form-group">
                <label for="modalItemTitle">标题</label>
                <input type="text" id="modalItemTitle" placeholder="请输入共创标题" required>
            </div>
            <div class="form-group">
                <label for="modalDesc">描述</label>
                <textarea id="modalDesc" rows="3" placeholder="请输入共创描述"></textarea>
            </div>
            <div class="form-group">
                <label for="modalLink">链接（可选）</label>
                <input type="text" id="modalLink" placeholder="activities.html 或 https://...">
            </div>
            <div class="form-group" style="display:flex; align-items:center; gap:10px;">
                <label class="switch" style="margin:0; display:inline-block;">
                    <input type="checkbox" id="modalVisible" checked>
                    <span class="slider"></span>
                </label>
                <label for="modalVisible" style="margin:0; font-size:14px; color:var(--text-dark); cursor:pointer;">在网站上显示</label>
            </div>
        `;
        document.getElementById('modalConfirmBtn').onclick = saveActivity;
    } else if (type === 'quickLinks') {
        editingQuickLinkIndex = -1;
        showQuickLinkModal();
    } else if (type === 'coreActivities') {
        editingCoreActivityIndex = -1;
        showCoreActivityModal();
    } else if (type === 'members') {
        editingMemberIndex = -1;
        showMemberModal();
    } else if (type === 'achievements') {
        editingAchievementIndex = -1;
        showAchievementModal();
    } else if (type === 'resources') {
        editingResourceIndex = -1;
        showResourceModal();
    } else if (type === 'books') {
        editingBookIndex = -1;
        showBookModal();
    } else if (type === 'organization') {
        editingOrgIndex = -1;
        showOrgModal();
    }
    document.getElementById('modal').style.display = 'flex';
}

function editActivity(index) {
    editingActivityIndex = index;
    const activity = currentData.activities[index];

    // 转换为 YYYY-MM-DD 格式
    const dateValue = parseDateForInput(activity.date);

    document.getElementById('modalTitle').textContent = '编辑共创';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalDate">日期</label>
            <input type="date" id="modalDate" value="${escapeHtml(dateValue)}" required>
        </div>
        <div class="form-group">
            <label for="modalItemTitle">标题</label>
            <input type="text" id="modalItemTitle" value="${escapeHtml(activity.title || '')}" required>
        </div>
        <div class="form-group">
            <label for="modalDesc">描述</label>
            <textarea id="modalDesc" rows="3">${escapeHtml(activity.desc || '')}</textarea>
        </div>
        <div class="form-group">
            <label for="modalLink">链接（可选）</label>
            <input type="text" id="modalLink" value="${escapeHtml(activity.link || '')}" placeholder="https://... 或 activities.html">
        </div>
        <div class="form-group" style="display:flex; align-items:center; gap:10px;">
            <label class="switch" style="margin:0; display:inline-block;">
                <input type="checkbox" id="modalVisible" ${activity.visible !== false ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
            <label for="modalVisible" style="margin:0; font-size:14px; color:var(--text-dark); cursor:pointer;">在网站上显示</label>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveActivity;
    document.getElementById('modal').style.display = 'flex';
}

async function saveActivity() {
    const dateInput = document.getElementById('modalDate').value;
    // flatpickr 返回 YYYY-MM-DD 格式，转换为中文格式保存
    const date = formatDateForSave(dateInput);
    const title = document.getElementById('modalItemTitle').value;
    const desc = document.getElementById('modalDesc').value;
    const link = document.getElementById('modalLink').value.trim();
    const visible = document.getElementById('modalVisible').checked;

    if (!date) {
        showToast('请输入日期', 'error');
        return;
    }

    if (!title) {
        showToast('请输入共创标题', 'error');
        return;
    }

    const item = { date, title, desc, link, visible: !!visible };

    try {
        const endpoint = editingActivityIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingActivityIndex >= 0
            ? { field: 'activities', index: editingActivityIndex, item }
            : { field: 'activities', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            const title = document.getElementById('modalItemTitle').value;
            showToast(editingActivityIndex >= 0 ? '共创已更新' : '共创已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderActivitiesTable();
            recordUpdate('activities', editingActivityIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteActivity(index) {
    showConfirm('确定要删除这条共创吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'activities', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('共创已删除', 'success');
            await loadCurrentData();
            renderActivitiesTable();
            recordUpdate('activities', 'delete', currentData.activities[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 快速入口管理 ============

let editingQuickLinkIndex = -1;

function editQuickLink(index) {
    editingQuickLinkIndex = index;
    const link = currentData.quickLinks[index];
    showQuickLinkModal(link);
    document.getElementById('modalTitle').textContent = '编辑快速入口';
}

function showQuickLinkModal(link = {}) {
    document.getElementById('modalTitle').textContent = link.title ? '编辑快速入口' : '添加快速入口';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalIcon">图标（Emoji）</label>
            <div class="emoji-picker-wrapper" style="position:relative;">
                <input type="text" id="modalIcon" class="emoji-input" value="${escapeHtml(link.icon || '📎')}" placeholder="📎">
                <button type="button" class="emoji-picker-trigger" onclick="toggleEmojiPicker('quickLinkEmojiPicker')">😊</button>
                <div id="quickLinkEmojiPicker" class="emoji-picker-dropdown"></div>
            </div>
        </div>
        <div class="form-group">
            <label for="modalTitleInput">标题</label>
            <input type="text" id="modalTitleInput" value="${escapeHtml(link.title || '')}" required>
        </div>
        <div class="form-group">
            <label for="modalDesc">描述</label>
            <input type="text" id="modalDesc" value="${escapeHtml(link.desc || '')}" placeholder="简短描述">
        </div>
        <div class="form-group">
            <label for="modalLink">链接</label>
            <input type="text" id="modalLink" value="${escapeHtml(link.link || '')}" placeholder="resources.html 或 https://...">
        </div>
    `;
    // 初始化 emoji 选择器
    const picker = document.getElementById('quickLinkEmojiPicker');
    if (picker) picker.innerHTML = generateEmojiPickerHtml();
    document.getElementById('modalConfirmBtn').onclick = saveQuickLink;
    openModal();
}

async function saveQuickLink() {
    const icon = document.getElementById('modalIcon').value || '📎';
    const title = document.getElementById('modalTitleInput').value.trim();
    const desc = document.getElementById('modalDesc').value.trim();
    const link = document.getElementById('modalLink').value.trim();

    if (!title) {
        showToast('请输入标题', 'error');
        return;
    }

    const item = { icon, title, desc, link };

    try {
        const endpoint = editingQuickLinkIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingQuickLinkIndex >= 0
            ? { field: 'quickLinks', index: editingQuickLinkIndex, item }
            : { field: 'quickLinks', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            const title = document.getElementById('modalTitleInput').value;
            showToast(editingQuickLinkIndex >= 0 ? '快速入口已更新' : '快速入口已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderQuickLinksTable();
            recordUpdate('quickLinks', editingQuickLinkIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteQuickLink(index) {
    showConfirm('确定要删除这个快速入口吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'quickLinks', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('快速入口已删除', 'success');
            await loadCurrentData();
            renderQuickLinksTable();
            recordUpdate('quickLinks', 'delete', currentData.quickLinks[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 核心共创管理 ============

let editingCoreActivityIndex = -1;

function editCoreActivity(index) {
    editingCoreActivityIndex = index;
    const activity = currentData.coreActivities[index];
    showCoreActivityModal(activity);
    document.getElementById('modalTitle').textContent = '编辑核心共创';
}

function showCoreActivityModal(activity = {}) {
    document.getElementById('modalTitle').textContent = activity.title ? '编辑核心共创' : '添加核心共创';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalIcon">图标（Emoji）</label>
            <div class="emoji-picker-wrapper" style="position:relative;">
                <input type="text" id="modalIcon" class="emoji-input" value="${escapeHtml(activity.icon || '📌')}" placeholder="📌">
                <button type="button" class="emoji-picker-trigger" onclick="toggleEmojiPicker('coreActivityEmojiPicker')">😊</button>
                <div id="coreActivityEmojiPicker" class="emoji-picker-dropdown"></div>
            </div>
        </div>
        <div class="form-group">
            <label for="modalTitleInput">标题</label>
            <input type="text" id="modalTitleInput" value="${escapeHtml(activity.title || '')}" required>
        </div>
        <div class="form-group">
            <label for="modalDesc">描述</label>
            <input type="text" id="modalDesc" value="${escapeHtml(activity.desc || '')}" placeholder="简短描述">
        </div>
        <div class="form-group">
            <label for="modalLink">链接（可选）</label>
            <input type="text" id="modalLink" value="${escapeHtml(activity.link || '')}" placeholder="activities.html 或 https://...">
        </div>
    `;
    // 初始化 emoji 选择器
    const picker = document.getElementById('coreActivityEmojiPicker');
    if (picker) picker.innerHTML = generateEmojiPickerHtml();
    document.getElementById('modalConfirmBtn').onclick = saveCoreActivity;
    openModal();
}

async function saveCoreActivity() {
    const icon = document.getElementById('modalIcon').value || '📌';
    const title = document.getElementById('modalTitleInput').value.trim();
    const desc = document.getElementById('modalDesc').value.trim();
    const link = document.getElementById('modalLink').value.trim();

    if (!title) {
        showToast('请输入标题', 'error');
        return;
    }

    const item = { icon, title, desc, link };

    try {
        const endpoint = editingCoreActivityIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingCoreActivityIndex >= 0
            ? { field: 'coreActivities', index: editingCoreActivityIndex, item }
            : { field: 'coreActivities', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            const title = document.getElementById('modalTitleInput').value;
            showToast(editingCoreActivityIndex >= 0 ? '核心共创已更新' : '核心共创已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderCoreActivitiesTable();
            recordUpdate('coreActivities', editingCoreActivityIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteCoreActivity(index) {
    showConfirm('确定要删除这个核心共创吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'coreActivities', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('核心共创已删除', 'success');
            await loadCurrentData();
            renderCoreActivitiesTable();
            recordUpdate('coreActivities', 'delete', currentData.coreActivities[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 成员管理 ============

let editingMemberIndex = -1;

async function toggleMemberVisible(index) {
    if (!currentData.members[index]) return;
    currentData.members[index].visible = !currentData.members[index].visible;

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_item',
                field: 'members',
                index: index,
                item: currentData.members[index]
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(currentData.members[index].visible ? '成员已显示' : '成员已隐藏', 'success');
        } else {
            // 回滚
            currentData.members[index].visible = !currentData.members[index].visible;
            renderMembersTable();
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    }
}

function editMember(index) {
    editingMemberIndex = index;
    const member = currentData.members[index];
    showMemberModal(member);
    document.getElementById('modalTitle').textContent = '编辑成员';
}

function showMemberModal(member = {}) {
    document.getElementById('modalTitle').textContent = member.name ? '编辑成员' : '添加成员';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalName">姓名</label>
            <input type="text" id="modalName" value="${escapeHtml(member.name || '')}" required>
        </div>
        <div class="form-group">
            <label for="modalGrade">加入年份</label>
            <input type="text" id="modalGrade" value="${escapeHtml(member.grade || '')}" placeholder="如：2024年加入">
        </div>
        <div class="form-group">
            <label for="modalField">方向</label>
            <input type="text" id="modalField" value="${escapeHtml(member.field || '')}" placeholder="如：平台运营">
        </div>
        <div class="form-group">
            <label for="modalBio">简介</label>
            <textarea id="modalBio" rows="3" placeholder="请输入个人简介">${escapeHtml(member.bio || '')}</textarea>
        </div>
        <div class="form-group">
            <label for="modalPhoto">照片URL</label>
            <input type="text" id="modalPhoto" value="${escapeHtml(member.photo || '')}" placeholder="留空使用默认头像">
        </div>
        <div class="form-group">
            <label for="modalLink">个人链接</label>
            <input type="text" id="modalLink" value="${escapeHtml(member.link || '')}" placeholder="个人主页、博客等（可选）">
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:10px;">
            <label class="switch" style="position:relative;display:inline-block;width:50px;height:24px;">
                <input type="checkbox" id="modalMemberVisible" ${member.visible !== false ? 'checked' : ''}>
                <span class="slider" style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background-color:#ccc;transition:.4s;border-radius:24px;"></span>
            </label>
            <label for="modalMemberVisible" style="margin:0;font-size:14px;color:var(--text-dark);cursor:pointer;">在网站上显示</label>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveMember;
    document.getElementById('modal').style.display = 'flex';
}

async function saveMember() {
    const name = document.getElementById('modalName').value;
    const grade = document.getElementById('modalGrade').value;
    const field = document.getElementById('modalField').value;
    const bio = document.getElementById('modalBio').value;
    const photo = document.getElementById('modalPhoto').value;
    const link = document.getElementById('modalLink').value;
    const visible = document.getElementById('modalMemberVisible').checked;

    if (!name) {
        showToast('请输入姓名', 'error');
        return;
    }

    const item = { name, grade, field, bio, photo, link, visible };

    try {
        const endpoint = editingMemberIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingMemberIndex >= 0
            ? { field: 'members', index: editingMemberIndex, item }
            : { field: 'members', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            const title = document.getElementById('modalName').value;
            showToast(editingMemberIndex >= 0 ? '成员已更新' : '成员已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderMembersTable();
            recordUpdate('members', editingMemberIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteMember(index) {
    showConfirm('确定要删除这位成员吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'members', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('成员已删除', 'success');
            await loadCurrentData();
            renderMembersTable();
            recordUpdate('members', 'delete', currentData.members[index]?.name || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 星社成就管理 ============

let editingAchievementIndex = -1;

function editAchievement(index) {
    editingAchievementIndex = index;
    const achievement = currentData.achievements[index];
    showAchievementModal(achievement);
    document.getElementById('modalTitle').textContent = '编辑成果';
}

function showAchievementModal(achievement = {}) {
    document.getElementById('modalTitle').textContent = editingAchievementIndex >= 0 ? '编辑成果' : '添加成果';
    // 转换日期为 YYYY-MM 格式，新建的默认当前年月
    let dateValue = getCurrentMonth();
    if (achievement.date) {
        const parsed = parseAchievementDateForInput(achievement.date);
        if (parsed) {
            dateValue = parsed;
        }
    }
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label>获奖年月</label>
            <input type="month" id="achievementDate" value="${escapeHtml(dateValue)}">
        </div>
        <div class="form-group">
            <label>奖项名称</label>
            <input type="text" id="achievementTitle" value="${escapeHtml(achievement.title || '')}" placeholder="例如：全国智慧创新竞赛一等奖">
        </div>
        <div class="form-group">
            <label>简介</label>
            <textarea id="achievementDesc" rows="3" placeholder="简短的成果介绍">${escapeHtml(achievement.desc || '')}</textarea>
        </div>
        <div class="form-group">
            <label>链接（可选）</label>
            <input type="text" id="achievementLink" value="${escapeHtml(achievement.link || '')}" placeholder="https://...">
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:10px;">
            <label class="switch">
                <input type="checkbox" id="achievementVisible" ${achievement.visible !== false ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
            <label for="achievementVisible" style="margin:0; font-size:14px; color:var(--text-dark); cursor:pointer;">在网站上显示</label>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveAchievement;
    openModal();
}

async function saveAchievement() {
    const dateInput = document.getElementById('achievementDate').value;
    // 转换为中文年月格式保存
    const date = formatMonthForSave(dateInput);
    const title = document.getElementById('achievementTitle').value.trim();
    const desc = document.getElementById('achievementDesc').value.trim();
    const link = document.getElementById('achievementLink').value.trim();
    const visible = document.getElementById('achievementVisible').checked;

    if (!date) {
        showToast('请输入获奖年月', 'error');
        return;
    }

    if (!title) {
        showToast('请输入奖项名称', 'error');
        return;
    }

    const item = { date, title, desc, link, visible };

    try {
        const endpoint = editingAchievementIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingAchievementIndex >= 0
            ? { field: 'achievements', index: editingAchievementIndex, item }
            : { field: 'achievements', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            showToast(editingAchievementIndex >= 0 ? '成果已更新' : '成果已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderAchievementsTable();
            recordUpdate('achievements', editingAchievementIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function toggleAchievementVisible(index) {
    try {
        const achievement = currentData.achievements[index];
        const newAchievement = { ...achievement, visible: !achievement.visible };

        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_activity',
                field: 'achievements',
                index: index,
                item: newAchievement
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(newAchievement.visible ? '成果已显示' : '成果已隐藏', 'success');
            await loadCurrentData();
            renderAchievementsTable();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    }
}

async function deleteAchievement(index) {
    showConfirm('确定要删除这个成果吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'achievements', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('成果已删除', 'success');
            await loadCurrentData();
            renderAchievementsTable();
            recordUpdate('achievements', 'delete', currentData.achievements[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 资源管理 ============

let editingResourceIndex = -1;

async function toggleResourceVisible(index) {
    if (!currentData.resources[index]) return;
    currentData.resources[index].visible = !currentData.resources[index].visible;

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_item',
                field: 'resources',
                index: index,
                item: currentData.resources[index]
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('更新成功', 'success');
        } else {
            // 回滚
            currentData.resources[index].visible = !currentData.resources[index].visible;
            renderResourcesTable();
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    }
}

function editResource(index) {
    editingResourceIndex = index;
    const resource = currentData.resources[index];
    showResourceModal(resource);
    document.getElementById('modalTitle').textContent = '编辑资源';
}

function showResourceModal(resource = {}) {
    document.getElementById('modalTitle').textContent = resource.title ? '编辑资源' : '添加资源';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalResIcon">图标</label>
            <div class="emoji-picker-wrapper" style="width: 100%;">
                <input type="text" id="modalResIcon" value="${escapeHtml(resource.icon || '📚')}" placeholder="如：📚、🔐" class="emoji-input" data-target="emoji-picker-resource" style="width: 100%;">
                <button type="button" class="emoji-picker-trigger" onclick="toggleEmojiPicker('emoji-picker-resource')">😊</button>
                <div id="emoji-picker-resource" class="emoji-picker-dropdown"></div>
            </div>
        </div>`;
    // 初始化 emoji 选择器内容
    setTimeout(() => {
        const picker = document.getElementById('emoji-picker-resource');
        if (picker) picker.innerHTML = generateEmojiPickerHtml();
    }, 0);
    document.getElementById('modalBody').innerHTML += `
        <div class="form-group">
            <label for="modalResTitle">标题</label>
            <input type="text" id="modalResTitle" value="${escapeHtml(resource.title || '')}" required>
        </div>
        <div class="form-group">
            <label for="modalResDesc">描述</label>
            <textarea id="modalResDesc" rows="3" placeholder="请输入资源描述">${escapeHtml(resource.desc || '')}</textarea>
        </div>
        <div class="form-group">
            <label for="modalResCategory">分类</label>
            <input type="text" id="modalResCategory" value="${escapeHtml(resource.category || '')}" placeholder="如：入门指南">
        </div>
        <div class="form-group">
            <label for="modalResLink">链接</label>
            <input type="text" id="modalResLink" value="${escapeHtml(resource.link || '')}" placeholder="如：# 或资源链接">
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:10px;">
            <label class="switch" style="position:relative;display:inline-block;width:50px;height:24px;">
                <input type="checkbox" id="modalResVisible" ${resource.visible !== false ? 'checked' : ''}>
                <span class="slider" style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background-color:#ccc;transition:.4s;border-radius:24px;"></span>
            </label>
            <label for="modalResVisible" style="margin:0;font-size:14px;color:var(--text-dark);cursor:pointer;">在网站上显示</label>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveResource;
    document.getElementById('modal').style.display = 'flex';
}

async function saveResource() {
    const icon = document.getElementById('modalResIcon').value;
    const title = document.getElementById('modalResTitle').value;
    const desc = document.getElementById('modalResDesc').value;
    const category = document.getElementById('modalResCategory').value;
    const link = document.getElementById('modalResLink').value;
    const visible = document.getElementById('modalResVisible').checked;

    if (!title) {
        showToast('请输入资源标题', 'error');
        return;
    }

    const item = { icon, title, desc, category, link, visible };

    try {
        const endpoint = editingResourceIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingResourceIndex >= 0
            ? { field: 'resources', index: editingResourceIndex, item }
            : { field: 'resources', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            const title = document.getElementById('modalResTitle').value;
            showToast(editingResourceIndex >= 0 ? '资源已更新' : '资源已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderResourcesTable();
            recordUpdate('resources', editingResourceIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteResource(index) {
    showConfirm('确定要删除这条资源吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'resources', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('资源已删除', 'success');
            await loadCurrentData();
            renderResourcesTable();
            recordUpdate('resources', 'delete', currentData.resources[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 批量导入功能 ============

let currentBatchImportField = '';
let currentBatchImportData = null;

function showBatchImportModal(field) {
    currentBatchImportField = field;
    currentBatchImportData = null;

    const titles = {
        'members': '成员风采 - 批量导入',
        'resources': '学习资源 - 批量导入'
    };

    document.getElementById('batchImportTitle').textContent = titles[field] || '批量导入';
    document.getElementById('batchImportFile').value = '';
    document.getElementById('batchImportFileName').textContent = '';
    document.getElementById('batchImportPreview').style.display = 'none';
    document.getElementById('batchImportConfirmBtn').disabled = true;

    document.getElementById('batchImportModal').style.display = 'flex';
}

function closeBatchImportModal() {
    document.getElementById('batchImportModal').style.display = 'none';
    currentBatchImportField = '';
    currentBatchImportData = null;
}

function downloadImportTemplate() {
    let csvContent = '';
    let filename = '';

    if (currentBatchImportField === 'members') {
        filename = 'members_template.csv';
        csvContent = '\uFEFF'; // BOM for UTF-8
        csvContent += '姓名,加入年份,方向,简介,照片URL,个人链接,显示\n';
        csvContent += '成员甲,2024年加入,平台运营,对智慧社团建设有浓厚兴趣,,,true\n';
        csvContent += '张三,2023年加入,应用开发,热爱创新实践,,https://example.com,true\n';
    } else if (currentBatchImportField === 'resources') {
        filename = 'resources_template.csv';
        csvContent = '\uFEFF';
        csvContent += '图标,标题,描述,分类,链接,显示\n';
        csvContent += '📚,智慧社团入门,适合初学者的智慧社团入门教程,入门指南,#,true\n';
        csvContent += '💡,创新工具集,常用创新实践工具介绍,工具推荐,#,false\n';
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast('模板文件已下载', 'success');
}

function handleBatchImportFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const fileName = file.name;
    document.getElementById('batchImportFileName').textContent = fileName;

    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        parseBatchImportCSV(content);
    };
    reader.readAsText(file, 'UTF-8');
}

function parseBatchImportCSV(content) {
    // 移除 UTF-8 BOM
    if (content.charCodeAt(0) === 0xFEFF) {
        content = content.slice(1);
    }

    const lines = content.split(/\r?\n/).filter(line => line.trim());
    if (lines.length < 2) {
        showToast('CSV 文件内容为空或格式错误', 'error');
        return;
    }

    // 解析 CSV（简单处理，考虑引号内可能有逗号）
    const headers = parseCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        if (values.length > 0 && values.some(v => v.trim())) {
            const row = {};
            headers.forEach((header, idx) => {
                row[header.trim()] = values[idx] || '';
            });
            rows.push(row);
        }
    }

    if (rows.length === 0) {
        showToast('CSV 文件没有有效数据行', 'error');
        return;
    }

    currentBatchImportData = rows;
    displayBatchImportPreview(rows);

    document.getElementById('batchImportPreview').style.display = 'block';
    document.getElementById('batchImportCount').textContent = rows.length;
    document.getElementById('batchImportConfirmBtn').disabled = false;
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
            if (inQuotes && line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += char;
        }
    }
    result.push(current);
    return result;
}

function displayBatchImportPreview(rows) {
    const container = document.getElementById('batchImportPreviewContent');

    if (currentBatchImportField === 'members') {
        container.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">姓名</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">加入年份</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">方向</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">简介</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.slice(0, 50).map(row => `
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['姓名'] || '')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['加入年份'] || '')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['方向'] || '')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml((row['简介'] || '').substring(0, 50))}${row['简介'] && row['简介'].length > 50 ? '...' : ''}</td>
                        </tr>
                    `).join('')}
                    ${rows.length > 50 ? `<tr><td colspan="4" style="padding: 8px; border: 1px solid #ddd; color: #888;">... 还有 ${rows.length - 50} 行未显示</td></tr>` : ''}
                </tbody>
            </table>
        `;
    } else if (currentBatchImportField === 'resources') {
        container.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">图标</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">标题</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">分类</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">描述</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.slice(0, 50).map(row => `
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['图标'] || '📚')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['标题'] || '')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(row['分类'] || '')}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml((row['描述'] || '').substring(0, 50))}${row['描述'] && row['描述'].length > 50 ? '...' : ''}</td>
                        </tr>
                    `).join('')}
                    ${rows.length > 50 ? `<tr><td colspan="4" style="padding: 8px; border: 1px solid #ddd; color: #888;">... 还有 ${rows.length - 50} 行未显示</td></tr>` : ''}
                </tbody>
            </table>
        `;
    }
}

async function confirmBatchImport() {
    if (!currentBatchImportData || currentBatchImportData.length === 0) {
        showToast('没有可导入的数据', 'error');
        return;
    }

    // 生成 CSV 字符串
    let csvContent = '\uFEFF';
    const headers = currentBatchImportField === 'members'
        ? ['姓名', '加入年份', '方向', '简介', '照片URL', '个人链接', '显示']
        : ['图标', '标题', '描述', '分类', '链接', '显示'];

    csvContent += headers.join(',') + '\n';
    currentBatchImportData.forEach(row => {
        const values = headers.map(h => {
            let val = (row[h] || '').toString();
            if (val.includes(',') || val.includes('"') || val.includes('\n')) {
                val = '"' + val.replace(/"/g, '""') + '"';
            }
            return val;
        });
        csvContent += values.join(',') + '\n';
    });

    try {
        const response = await fetch('/api/batch-import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                field: currentBatchImportField,
                csv: csvContent
            })
        });

        const result = await response.json();
        if (result.success) {
            // 在关闭模态框之前保存 field 类型
            const importField = currentBatchImportField;

            showToast(result.message, 'success');
            closeBatchImportModal();
            await loadCurrentData();

            if (importField === 'members') {
                renderMembersTable();
            } else if (importField === 'resources') {
                renderResourcesTable();
            }

            updateDashboardStats();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('导入失败: ' + error.message, 'error');
        console.error('批量导入错误:', error);
    }
}

// ============ 星社机制管理 ============

let editingOrgIndex = -1;

async function toggleOrgVisible(index) {
    if (!currentData.organization[index]) return;
    currentData.organization[index].visible = !currentData.organization[index].visible;

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_item',
                field: 'organization',
                index: index,
                item: currentData.organization[index]
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast('更新成功', 'success');
        } else {
            // 回滚
            currentData.organization[index].visible = !currentData.organization[index].visible;
            renderOrganizationTable();
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    }
}

function showOrgModal(org = {}) {
    document.getElementById('modalTitle').textContent = org.name ? '编辑部门' : '添加部门';
    const positionsValue = org.positions ? org.positions.join('\n') : '';
    const isVisible = org.visible !== false;
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="orgIcon">部门图标</label>
            <div class="emoji-picker-wrapper" style="display:flex;gap:8px;">
                <input type="text" id="orgIcon" class="emoji-input" value="${escapeHtml(org.icon || '📌')}" placeholder="选择一个图标" style="flex:1;">
                <button type="button" class="emoji-picker-trigger" onclick="toggleEmojiPicker('emoji-picker-org')">😊</button>
                <div id="emoji-picker-org" class="emoji-picker-dropdown"></div>
            </div>
        </div>
        <div class="form-group">
            <label for="orgName">部门名称</label>
            <input type="text" id="orgName" value="${escapeHtml(org.name || '')}" placeholder="如：运营组、创新研究组" required>
        </div>
        <div class="form-group">
            <label for="orgDesc">部门职责</label>
            <textarea id="orgDesc" rows="3" placeholder="请输入部门职责描述">${escapeHtml(org.description || '')}</textarea>
        </div>
        <div class="form-group">
            <label for="orgPositions">职位设置（每行一条）</label>
            <textarea id="orgPositions" rows="4" placeholder="每行一条职位，如：&#10;组长 1名&#10;副组长 2名&#10;骨干若干">${escapeHtml(positionsValue)}</textarea>
            <small style="color:#888;font-size:11px;">每行代表一个职位说明</small>
        </div>
        <div class="form-group" style="display:flex; align-items:center; gap:10px;">
            <label for="orgVisible" style="margin:0;">是否显示</label>
            <label class="switch" style="margin:0; display:inline-block;">
                <input type="checkbox" id="orgVisible" ${isVisible ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveOrg;
    document.getElementById('modal').style.display = 'flex';
    // 初始化emoji选择器
    initEmojiPickers();
}

function editOrg(index) {
    editingOrgIndex = index;
    const org = currentData.organization[index];
    showOrgModal(org);
    document.getElementById('modalTitle').textContent = '编辑部门';
}

async function saveOrg() {
    const icon = document.getElementById('orgIcon').value;
    const name = document.getElementById('orgName').value;
    const description = document.getElementById('orgDesc').value;
    const positionsText = document.getElementById('orgPositions').value;
    const positions = positionsText.split('\n').filter(p => p.trim() !== '');
    const visible = document.getElementById('orgVisible').checked;

    if (!name) {
        showToast('请输入部门名称', 'error');
        return;
    }

    const item = { name, description, visible };
    if (icon) item.icon = icon;
    if (positions.length > 0) item.positions = positions;

    try {
        const endpoint = editingOrgIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingOrgIndex >= 0
            ? { field: 'organization', index: editingOrgIndex, item }
            : { field: 'organization', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            showToast(editingOrgIndex >= 0 ? '部门已更新' : '部门已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderOrganizationTable();
            recordUpdate('organization', editingOrgIndex >= 0 ? 'edit' : 'add', name);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteOrg(index) {
    showConfirm('确定要删除这个部门吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'organization', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('部门已删除', 'success');
            await loadCurrentData();
            renderOrganizationTable();
            recordUpdate('organization', 'delete', currentData.organization[index]?.name || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 推荐书籍管理 ============
let editingBookIndex = -1;

function renderBooksTable() {
    const tbody = document.getElementById('booksTableBody');
    if (!tbody) return;

    const books = currentData.books || [];
    if (books.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-light);padding:20px;">暂无书籍，点击上方"添加书籍"创建</td></tr>';
        return;
    }

    tbody.innerHTML = books.map((book, index) => `
        <tr>
            <td><strong>${escapeHtml(book.title || '')}</strong></td>
            <td>${escapeHtml(book.author || '-')}</td>
            <td style="max-width:300px;">${escapeHtml(book.desc || '-')}</td>
            <td>
                <button class="btn-tiny btn-edit" onclick="editBook(${index})">编辑</button>
                <button class="btn-tiny btn-delete" onclick="deleteBook(${index})">删除</button>
            </td>
        </tr>
    `).join('');
}

function showBookModal(book = {}) {
    document.getElementById('modalTitle').textContent = book.title ? '编辑书籍' : '添加书籍';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="modalBookTitle">书名 <span style="color:red">*</span></label>
            <input type="text" id="modalBookTitle" value="${escapeHtml(book.title || '')}" placeholder="如：智慧社团建设" required>
        </div>
        <div class="form-group">
            <label for="modalBookAuthor">作者</label>
            <input type="text" id="modalBookAuthor" value="${escapeHtml(book.author || '')}" placeholder="如：William Stallings">
        </div>
        <div class="form-group">
            <label for="modalBookDesc">简介</label>
            <textarea id="modalBookDesc" rows="3" placeholder="请输入书籍简介">${escapeHtml(book.desc || '')}</textarea>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = saveBook;
    document.getElementById('modal').style.display = 'flex';
}

function editBook(index) {
    editingBookIndex = index;
    const book = currentData.books[index];
    showBookModal(book);
    document.getElementById('modalTitle').textContent = '编辑书籍';
}

async function saveBook() {
    const title = document.getElementById('modalBookTitle').value;
    const author = document.getElementById('modalBookAuthor').value;
    const desc = document.getElementById('modalBookDesc').value;

    if (!title) {
        showToast('请输入书名', 'error');
        return;
    }

    const item = { title, author, desc };

    try {
        const endpoint = editingBookIndex >= 0 ? 'update_activity' : 'add_item';
        const payload = editingBookIndex >= 0
            ? { field: 'books', index: editingBookIndex, item }
            : { field: 'books', item };

        const payloadData = { action: endpoint, ...payload };
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const result = await response.json();
        if (result.success) {
            showToast(editingBookIndex >= 0 ? '书籍已更新' : '书籍已添加', 'success');
            closeModal();
            await loadCurrentData();
            renderBooksTable();
            recordUpdate('books', editingBookIndex >= 0 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

async function deleteBook(index) {
    showConfirm('确定要删除这本书吗？', async () => {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete_item', field: 'books', index })
        });

        const result = await response.json();
        if (result.success) {
            showToast('书籍已删除', 'success');
            await loadCurrentData();
            renderBooksTable();
            recordUpdate('books', 'delete', currentData.books[index]?.title || '');
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ============ 表单处理 ============

/**
 * 标记字段已修改
 */
function markFieldAsChanged(field) {
    if (!field.classList.contains('changed')) {
        field.classList.add('changed');
        updateChangedCount();
    }
}

/**
 * 更新修改计数
 */
function updateChangedCount() {
    const changedFields = document.querySelectorAll('.changed');
    const countEl = document.getElementById('changedCount');
    if (countEl) {
        countEl.textContent = changedFields.length;
    }
}

/**
 * 处理表单提交
 */
async function handleFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formId = form.id;

    try {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        let section = 'all';
        if (formId === 'heroForm') section = 'hero';
        else if (formId === 'statsForm') section = 'stats';
        else if (formId === 'aboutForm') section = 'about';
        else if (formId === 'advisorForm') section = 'advisor';
        else if (formId === 'contactForm') section = 'contact';
        else if (formId === 'joinForm') section = 'join';
        else if (formId === 'footerForm') section = 'footer';

        // 收集所有数据用于 stats 部分
        if (formId === 'statsForm') {
            data.foundedYear = formData.get('foundedYear');
            data.memberCount = formData.get('memberCount');
            data.activityCount = formData.get('activityCount');
            data.foundedYearLabel = formData.get('foundedYearLabel');
            data.memberCountLabel = formData.get('memberCountLabel');
            data.activityCountLabel = formData.get('activityCountLabel');
        }

        // 收集页脚子项数据
        if (formId === 'footerForm') {
            const footerItems = collectFooterItems();
            Object.assign(data, footerItems);
        }

        // 收集FAQ数据
        if (formId === 'joinForm') {
            data.faq = collectFaqItems();
        }

        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ section, data })
        });

        const result = await response.json();

        if (result.success) {
            showToast('保存成功', 'success');
            form.querySelectorAll('.changed').forEach(el => el.classList.remove('changed'));
            updateChangedCount();
            await loadCurrentData();
        } else {
            throw new Error(result.error || '保存失败');
        }
    } catch (error) {
        console.error('保存失败:', error);
        showToast('保存失败: ' + error.message, 'error');
    }
}

/**
 * 保存所有更改
 */
async function saveAllChanges() {
    const allFields = {};

    document.querySelectorAll('.section form').forEach(form => {
        const formData = new FormData(form);
        for (let [key, value] of formData.entries()) {
            allFields[key] = value;
        }
    });

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ section: 'all', data: allFields })
        });

        const result = await response.json();

        if (result.success) {
            showToast('全部保存成功', 'success');
            document.querySelectorAll('.changed').forEach(el => el.classList.remove('changed'));
            updateChangedCount();
            await loadCurrentData();
        } else {
            throw new Error(result.error || '保存失败');
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

/**
 * 预览更改
 */
function previewChanges() {
    const changedFields = document.querySelectorAll('.changed');
    if (changedFields.length === 0) {
        showToast('暂无更改', 'info');
        return;
    }

    let preview = '以下字段已修改：\n';
    changedFields.forEach(field => {
        preview += `- ${field.name || field.id}: ${field.value.substring(0, 50)}${field.value.length > 50 ? '...' : ''}\n`;
    });
    showToast(preview, 'info');
}

// ============ 弹窗与提示 ============

// 自定义确认弹窗回调
let _confirmCallback = null;

/**
 * 显示自定义确认弹窗（替代原生confirm）
 * @param {string} message - 提示消息
 * @param {Function} onConfirm - 确认后的回调
 * @param {string} [title='确认操作'] - 弹窗标题
 */
function showConfirm(message, onConfirm, title = '确认操作') {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMessage').textContent = message;
    _confirmCallback = onConfirm;
    document.getElementById('confirmModal').style.display = 'flex';
}

function openModal() {
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

function confirmModal() {
    // 由具体功能自行处理
}

function closePreviewModal() {
    document.getElementById('previewModal').style.display = 'none';
}

function closeConfirmModal() {
    document.getElementById('confirmModal').style.display = 'none';
    _confirmCallback = null;
}

function confirmAction() {
    if (_confirmCallback) {
        _confirmCallback();
        _confirmCallback = null;
    }
    closeConfirmModal();
}

function showDetailModal() { showToast('请使用新的详情页编辑器', 'info'); }
function closeDetailModal() {
    document.getElementById('detailModal').style.display = 'none';
}
function saveDetail() { showToast('请使用新的详情页编辑器', 'info'); }
function showCategoryModal() { showToast('功能开发中', 'info'); }
function closeCategoryModal() {
    document.getElementById('categoryModal').style.display = 'none';
}
function saveCategory() { showToast('功能开发中', 'info'); }

// ============ 详情页编辑器 ============

let dpEditingIndex = -1;    // 当前编辑的详情页索引，-1为新建
let dpSections = [];        // 当前编辑的板块列表

/**
 * 加载并渲染详情页列表
 */
async function loadDetailPages() {
    const container = document.getElementById('detailsList');
    if (!container) return;

    try {
        const response = await fetch('/api/detail-pages');
        const result = await response.json();

        if (result.success && result.pages && result.pages.length > 0) {
            container.innerHTML = result.pages.map((page, index) => {
                const filename = page.filename || `detail-${index}.html`;
                const pagePath = `pages/${filename}`;
                const sectionCount = (page.sections || []).length;
                const typeIcons = {heading:'📋',text:'📝',cards:'🃏',image:'🖼️',video:'🎬',audio:'🎵',html:'🔧',markdown:'📑'};
                const typeSummary = (page.sections || []).map(s => typeIcons[s.type] || '📦').join(' ');

                return `
                    <div class="detail-card">
                        <div class="detail-card-header">
                            <h4>
                                <span style="margin-right:8px;font-size:20px;">${escapeHtml(page.icon || '📄')}</span>
                                ${escapeHtml(page.title || '无标题')}
                                ${page.subtitle ? `<span style="font-weight:normal;color:var(--text-light);font-size:13px;margin-left:8px;">${escapeHtml(page.subtitle)}</span>` : ''}
                            </h4>
                            <div class="detail-card-actions">
                                <a href="/${escapeHtml(pagePath)}" target="_blank" class="btn btn-tiny btn-primary" style="color:white;text-decoration:none;">预览</a>
                                <button class="btn-tiny btn-edit" onclick="editDetailPage(${index})">编辑</button>
                                <button class="btn-tiny" onclick="copyDetailPagePath('${escapeHtml(pagePath)}')">复制地址</button>
                                <button class="btn-tiny btn-edit" onclick="duplicateDetailPage(${index})">复制</button>
                                <button class="btn-tiny btn-delete" onclick="deleteDetailPage(${index})">删除</button>
                            </div>
                        </div>
                        <div class="detail-card-content" style="display:flex;gap:20px;align-items:center;">
                            <span style="font-size:12px;color:var(--text-light);">
                                🔗 <code style="background:#f0f0f0;padding:2px 8px;border-radius:4px;">${escapeHtml(pagePath)}</code>
                            </span>
                            <span style="font-size:12px;color:var(--text-light);">
                                📦 ${sectionCount} 个板块
                            </span>
                            <span style="font-size:12px;" title="板块类型">${typeSummary}</span>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = `
                <div style="text-align:center;padding:60px 20px;color:var(--text-light);">
                    <div style="font-size:48px;margin-bottom:16px;">📄</div>
                    <p style="font-size:16px;margin-bottom:8px;">暂无详情页</p>
                    <p style="font-size:13px;">点击「新建详情页」开始创建自定义页面</p>
                </div>
            `;
        }
    } catch (error) {
        container.innerHTML = '<p style="text-align:center;color:#999;">加载失败</p>';
        console.error('加载详情页失败:', error);
    }
}

/**
 * 打开新建详情页编辑器
 */
function showDetailPageEditor() {
    dpEditingIndex = -1;
    dpSections = [];

    document.getElementById('detailModalTitle').textContent = '新建详情页';
    document.getElementById('dpTitle').value = '';
    document.getElementById('dpSubtitle').value = '';
    document.getElementById('dpFilename').value = '';
    document.getElementById('dpIcon').value = '';

    renderDpSections();
    document.getElementById('detailModal').style.display = 'flex';
}

/**
 * 编辑已有详情页
 */
async function editDetailPage(index) {
    try {
        const response = await fetch('/api/detail-pages');
        const result = await response.json();
        if (!result.success) throw new Error('加载失败');

        const page = result.pages[index];
        if (!page) throw new Error('页面不存在');

        // 使用 filename 作为唯一标识，而不是数组 index
        dpEditingIndex = page.filename;
        dpSections = JSON.parse(JSON.stringify(page.sections || []));

        document.getElementById('detailModalTitle').textContent = '编辑详情页';
        document.getElementById('dpTitle').value = page.title || '';
        document.getElementById('dpSubtitle').value = page.subtitle || '';
        document.getElementById('dpFilename').value = page.filename || '';
        document.getElementById('dpIcon').value = page.icon || '';

        renderDpSections();
        document.getElementById('detailModal').style.display = 'flex';
    } catch (error) {
        showToast('加载详情页失败: ' + error.message, 'error');
    }
}

/**
 * 删除详情页
 */
async function deleteDetailPage(index) {
    showConfirm('确定要删除这个详情页吗？删除后无法恢复。', async () => {
    try {
        // 先获取页面信息（使用 filename 定位）
        const response = await fetch('/api/detail-pages');
        const result = await response.json();
        if (!result.success) throw new Error('加载失败');

        const page = result.pages[index];
        if (!page) throw new Error('页面不存在');

        const filename = page.filename;
        const pageTitle = page.title;

        // 使用 filename 删除
        const deleteResponse = await fetch(`/api/detail-pages/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        const deleteResult = await deleteResponse.json();
        if (deleteResult.success) {
            showToast('详情页已删除', 'success');
            await loadDetailPages();
            await loadCurrentData();
            recordUpdate('detailPages', 'delete', pageTitle);
        } else {
            throw new Error(deleteResult.error);
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

/**
 * 复制详情页地址
 */
function copyDetailPagePath(path) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(path).then(() => {
            showToast('地址已复制: ' + path, 'success');
        }).catch(() => {
            fallbackCopy(path, path);
        });
    } else {
        fallbackCopy(path, path);
    }
}

function fallbackCopy(text, label) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        showToast('地址已复制: ' + label, 'success');
    } catch (e) {
        showToast('复制失败', 'error');
    }
    document.body.removeChild(textarea);
}

/**
 * 复制详情页（复制为新页面）
 */
async function duplicateDetailPage(index) {
    try {
        const response = await fetch('/api/detail-pages');
        const result = await response.json();
        if (!result.success) throw new Error('加载失败');

        const page = result.pages[index];
        if (!page) throw new Error('页面不存在');

        const originalFilename = page.filename || `detail-${index}.html`;
        const defaultFilename = originalFilename.replace('.html', '-copy.html');

        document.getElementById('modalTitle').textContent = '复制详情页';
        document.getElementById('modalBody').innerHTML = `
            <div class="form-group">
                <label for="duplicateNewTitle">新页面标题</label>
                <input type="text" id="duplicateNewTitle" value="${escapeHtml(page.title + '（副本）')}" placeholder="输入新页面标题">
            </div>
            <div class="form-group">
                <label for="duplicateNewFilename">新页面文件名</label>
                <input type="text" id="duplicateNewFilename" value="${escapeHtml(defaultFilename)}" placeholder="输入新文件名">
                <p style="font-size:12px;color:var(--text-light);margin-top:8px;">提示：如未输入扩展名，将自动添加 .html</p>
            </div>
        `;
        document.getElementById('modalConfirmBtn').onclick = async function() {
            const newTitle = document.getElementById('duplicateNewTitle').value.trim() || page.title + '（副本）';
            const newFilename = document.getElementById('duplicateNewFilename').value.trim() || defaultFilename;
            const finalFilename = newFilename.endsWith('.html') ? newFilename : newFilename + '.html';

            const newPage = {
                ...page,
                title: newTitle,
                filename: finalFilename
            };

            try {
                const saveResponse = await fetch('/api/detail-pages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ page: newPage, id: null })
                });
                const saveResult = await saveResponse.json();
                if (saveResult.success) {
                    showToast('详情页已复制', 'success');
                    closeModal();
                    await loadDetailPages();
                    await loadCurrentData();
                    recordUpdate('detailPages', 'add', newTitle);
                } else {
                    throw new Error(saveResult.error);
                }
            } catch (error) {
                showToast('复制失败: ' + error.message, 'error');
            }
        };
        openModal();
    } catch (error) {
        showToast('复制失败: ' + error.message, 'error');
    }
}

/**
 * 添加板块
 */
function dpAddSection(type) {
    // 先收集当前编辑的内容，避免丢失
    dpCollectData();

    const defaults = {
        heading: { type: 'heading', content: '' },
        text: { type: 'text', content: '' },
        cards: { type: 'cards', items: [{ icon: '', title: '', desc: '', link: '' }] },
        image: { type: 'image', src: '', alt: '', caption: '' },
        video: { type: 'video', src: '', embed: '', poster: '', caption: '' },
        audio: { type: 'audio', src: '', caption: '' },
        html: { type: 'html', content: '' },
        markdown: { type: 'markdown', content: '' }
    };

    dpSections.push({ ...defaults[type] });
    renderDpSections();
}

/**
 * 删除板块
 */
function dpRemoveSection(index) {
    dpCollectData();
    dpSections.splice(index, 1);
    renderDpSections();
}

/**
 * 上移板块
 */
function dpMoveSectionUp(index) {
    if (index <= 0) return;
    dpCollectData();
    [dpSections[index - 1], dpSections[index]] = [dpSections[index], dpSections[index - 1]];
    renderDpSections();
}

/**
 * 下移板块
 */
function dpMoveSectionDown(index) {
    if (index >= dpSections.length - 1) return;
    dpCollectData();
    [dpSections[index], dpSections[index + 1]] = [dpSections[index + 1], dpSections[index]];
    renderDpSections();
}

/**
 * 添加卡片项（cards类型板块内）
 */
function dpAddCard(sectionIndex) {
    dpCollectData();
    if (!dpSections[sectionIndex].items) dpSections[sectionIndex].items = [];
    dpSections[sectionIndex].items.push({ icon: '', title: '', desc: '', link: '' });
    renderDpSections();
}

/**
 * 删除卡片项
 */
function dpRemoveCard(sectionIndex, cardIndex) {
    dpCollectData();
    dpSections[sectionIndex].items.splice(cardIndex, 1);
    renderDpSections();
}

/**
 * 从编辑器DOM收集数据到dpSections
 */
function dpCollectData() {
    dpSections.forEach((section, i) => {
        const sectionEl = document.querySelector(`[data-dp-section="${i}"]`);
        if (!sectionEl) return;

        if (section.type === 'heading') {
            section.content = sectionEl.querySelector('.dp-heading-content')?.value || '';
        } else if (section.type === 'text') {
            section.content = sectionEl.querySelector('.dp-text-content')?.value || '';
        } else if (section.type === 'cards') {
            const cards = sectionEl.querySelectorAll('.dp-card-item');
            section.items = Array.from(cards).map(card => ({
                icon: card.querySelector('.dp-card-icon')?.value || '',
                title: card.querySelector('.dp-card-title')?.value || '',
                desc: card.querySelector('.dp-card-desc')?.value || '',
                link: card.querySelector('.dp-card-link')?.value || ''
            }));
        } else if (section.type === 'image') {
            section.src = sectionEl.querySelector('.dp-img-src')?.value || '';
            section.alt = sectionEl.querySelector('.dp-img-alt')?.value || '';
            section.caption = sectionEl.querySelector('.dp-img-caption')?.value || '';
        } else if (section.type === 'video') {
            section.src = sectionEl.querySelector('.dp-video-src')?.value || '';
            section.embed = sectionEl.querySelector('.dp-video-embed')?.value || '';
            section.poster = sectionEl.querySelector('.dp-video-poster')?.value || '';
            section.caption = sectionEl.querySelector('.dp-video-caption')?.value || '';
        } else if (section.type === 'audio') {
            section.src = sectionEl.querySelector('.dp-audio-src')?.value || '';
            section.caption = sectionEl.querySelector('.dp-audio-caption')?.value || '';
        } else if (section.type === 'html') {
            section.content = sectionEl.querySelector('.dp-html-content')?.value || '';
        } else if (section.type === 'markdown') {
            section.content = sectionEl.querySelector('.dp-md-content')?.value || '';
        }
    });
}

/**
 * 渲染板块列表
 */
function renderDpSections() {
    const container = document.getElementById('dpSectionsContainer');
    if (!container) return;

    if (dpSections.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:#999;background:#f9f9f9;border-radius:12px;border:2px dashed #ddd;">点击上方按钮添加板块，构建您的页面内容</div>';
        return;
    }

    const typeNames = { heading: '二级标题', text: '富文本', cards: '卡片组', image: '图片', video: '视频', audio: '音频', html: '内嵌HTML', markdown: 'Markdown' };
    const typeColors = { heading: '#6366f1', text: '#3b82f6', cards: '#f59e0b', image: '#10b981', video: '#ef4444', audio: '#ec4899', html: '#8b5cf6', markdown: '#06b6d4' };

    container.innerHTML = dpSections.map((section, i) => {
        const name = typeNames[section.type] || section.type;
        const color = typeColors[section.type] || '#6b7280';

        let contentHtml = '';
        if (section.type === 'heading') {
            contentHtml = `<input type="text" class="dp-heading-content" value="${escapeHtml(section.content || '')}" placeholder="输入二级标题文字" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:15px;font-weight:600;">`;
        } else if (section.type === 'text') {
            contentHtml = `<textarea class="dp-text-content" rows="5" placeholder="输入富文本内容，支持HTML标签" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:14px;resize:vertical;">${escapeHtml(section.content || '')}</textarea>`;
        } else if (section.type === 'cards') {
            const cardsHtml = (section.items || []).map((card, ci) => `
                <div class="dp-card-item" style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin-bottom:10px;position:relative;">
                    <button type="button" onclick="dpRemoveCard(${i},${ci})" class="btn-tiny btn-delete" style="position:absolute;top:8px;right:8px;">删除</button>
                    <div style="display:grid;grid-template-columns:60px 1fr 1fr;gap:8px;margin-bottom:8px;">
                        <div><label style="font-size:11px;color:#888;">图标</label><input type="text" class="dp-card-icon" value="${escapeHtml(card.icon || '')}" placeholder="📚" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:13px;"></div>
                        <div><label style="font-size:11px;color:#888;">标题</label><input type="text" class="dp-card-title" value="${escapeHtml(card.title || '')}" placeholder="卡片标题" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:13px;"></div>
                        <div><label style="font-size:11px;color:#888;">链接</label><input type="text" class="dp-card-link" value="${escapeHtml(card.link || '')}" placeholder="可选链接" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:13px;"></div>
                    </div>
                    <div><label style="font-size:11px;color:#888;">描述</label><textarea class="dp-card-desc" rows="2" placeholder="卡片描述" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:13px;resize:vertical;">${escapeHtml(card.desc || '')}</textarea></div>
                </div>
            `).join('');
            contentHtml = cardsHtml + `<button type="button" onclick="dpAddCard(${i})" class="btn btn-secondary" style="width:100%;">+ 添加卡片</button>`;
        } else if (section.type === 'image') {
            contentHtml = `
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
                    <div><label style="font-size:11px;color:#888;">图片链接</label><input type="text" class="dp-img-src" value="${escapeHtml(section.src || '')}" placeholder="如：uploads/images/photo.jpg" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                    <div><label style="font-size:11px;color:#888;">替代文本</label><input type="text" class="dp-img-alt" value="${escapeHtml(section.alt || '')}" placeholder="图片描述（可选）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                </div>
                <div><label style="font-size:11px;color:#888;">图片说明</label><input type="text" class="dp-img-caption" value="${escapeHtml(section.caption || '')}" placeholder="显示在图片下方的说明文字（可选）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
            `;
        } else if (section.type === 'video') {
            contentHtml = `
                <div style="margin-bottom:8px;"><label style="font-size:11px;color:#888;">视频文件链接</label><input type="text" class="dp-video-src" value="${escapeHtml(section.src || '')}" placeholder="如：uploads/videos/demo.mp4（与嵌入链接二选一）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                <div style="margin-bottom:8px;"><label style="font-size:11px;color:#888;">视频嵌入链接</label><input type="text" class="dp-video-embed" value="${escapeHtml(section.embed || '')}" placeholder="如：https://www.bilibili.com/video/... 的嵌入链接" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <div><label style="font-size:11px;color:#888;">封面图</label><input type="text" class="dp-video-poster" value="${escapeHtml(section.poster || '')}" placeholder="视频封面图链接（可选）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                    <div><label style="font-size:11px;color:#888;">视频说明</label><input type="text" class="dp-video-caption" value="${escapeHtml(section.caption || '')}" placeholder="视频说明文字（可选）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                </div>
            `;
        } else if (section.type === 'audio') {
            contentHtml = `
                <div style="margin-bottom:8px;"><label style="font-size:11px;color:#888;">音频文件链接</label><input type="text" class="dp-audio-src" value="${escapeHtml(section.src || '')}" placeholder="如：uploads/audios/demo.mp3" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
                <div><label style="font-size:11px;color:#888;">音频说明</label><input type="text" class="dp-audio-caption" value="${escapeHtml(section.caption || '')}" placeholder="音频说明文字（可选）" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;"></div>
            `;
        } else if (section.type === 'html') {
            contentHtml = `<textarea class="dp-html-content" rows="8" placeholder="输入HTML代码，将直接渲染到页面上" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-family:'Courier New',monospace;font-size:13px;resize:vertical;">${escapeHtml(section.content || '')}</textarea>`;
        } else if (section.type === 'markdown') {
            contentHtml = `<textarea class="dp-md-content" rows="8" placeholder="输入Markdown内容，将自动渲染为HTML" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-family:'Courier New',monospace;font-size:13px;resize:vertical;">${escapeHtml(section.content || '')}</textarea>
            <small style="color:#888;font-size:11px;">支持标题(#)、粗体(**)、链接([]())、代码(\`)、列表(-)、引用(>)、表格等Markdown语法</small>`;
        }

        return `
            <div data-dp-section="${i}" class="dp-section-block" style="background:#f9f9fb;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;color:#fff;background:${color};">${name}</span>
                        <span style="font-size:11px;color:#aaa;">板块 ${i + 1}</span>
                    </div>
                    <div style="display:flex;gap:4px;">
                        <button type="button" onclick="dpMoveSectionUp(${i})" title="上移" class="btn-tiny" ${i === 0 ? 'disabled' : ''}>↑</button>
                        <button type="button" onclick="dpMoveSectionDown(${i})" title="下移" class="btn-tiny" ${i === dpSections.length - 1 ? 'disabled' : ''}>↓</button>
                        <button type="button" onclick="dpRemoveSection(${i})" title="删除板块" class="btn-tiny btn-delete">删除</button>
                    </div>
                </div>
                ${contentHtml}
            </div>
        `;
    }).join('');
}

/**
 * 保存详情页
 */
async function dpSavePage() {
    const title = document.getElementById('dpTitle').value.trim();
    if (!title) {
        showToast('请输入页面标题', 'error');
        return;
    }

    // 先从DOM收集最新数据
    dpCollectData();

    let filename = document.getElementById('dpFilename').value.trim();
    if (!filename) {
        // 自动生成文件名：从标题提取拼音或用序号
        filename = `detail-${dpEditingIndex >= 0 ? dpEditingIndex : Date.now()}.html`;
    }
    if (!filename.endsWith('.html')) filename += '.html';

    const pageData = {
        title: title,
        subtitle: document.getElementById('dpSubtitle').value.trim(),
        filename: filename,
        icon: document.getElementById('dpIcon').value.trim() || '📄',
        sections: dpSections
    };

    try {
        const response = await fetch('/api/detail-pages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: dpEditingIndex !== -1 ? dpEditingIndex : null,
                page: pageData
            })
        });

        const result = await response.json();
        if (result.success) {
            // 自动生成HTML文件到 pages/ 目录
            try {
                const pageId = result.id;
                if (pageId !== undefined && pageId !== null) {
                    await fetch(`/api/detail-pages/generate/${pageId}`, { method: 'POST' });
                }
            } catch (e) {
                console.warn('自动生成HTML失败:', e);
            }
            showToast(dpEditingIndex !== -1 ? '详情页已更新' : '详情页已创建', 'success');
            closeDetailModal();
            await loadDetailPages();
            await loadCurrentData();
            recordUpdate('detailPages', dpEditingIndex !== -1 ? 'edit' : 'add', title);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

/**
 * 显示提示消息
 */
function showToast(message, type = 'info') {
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) existingToast.remove();

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
        <span class="toast-message">${message}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * HTML转义
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// 添加样式
const style = document.createElement('style');
style.textContent = `
    .toast-notification {
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        background: #333;
        color: white;
        display: flex;
        align-items: center;
        gap: 10px;
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s ease;
        z-index: 10000;
        font-size: 14px;
    }
    .toast-notification.show {
        opacity: 1;
        transform: translateY(0);
    }
    .toast-success { background: #10b981; }
    .toast-error { background: #ef4444; }
    .toast-info { background: #3b82f6; }
    .toast-icon { font-weight: bold; }
    .changed {
        border-color: #f59e0b !important;
        background-color: #fef3c7 !important;
    }
    .btn-tiny {
        padding: 4px 8px;
        font-size: 12px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        margin-right: 4px;
    }
    .btn-edit { background: #3b82f6; color: white; }
    .btn-delete { background: #ef4444; color: white; }
    .btn-preview, .btn-save-all {
        padding: 10px 20px;
        font-size: 14px;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }
    .btn-preview { background: #6b7280; color: white; }
    .btn-save-all { background: #10b981; color: white; }
    .loading-bar {
        width: 100%;
        height: 8px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
    }
    .loading-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #10b981);
        border-radius: 4px;
        transition: width 0.3s ease;
    }
`;
document.head.appendChild(style);

// ============ 静态网站导出功能 ============

let isExporting = false;

/**
 * 一键导出所有静态页面
 */
async function exportAllStatic() {
    if (isExporting) {
        showToast('正在导出中，请稍候...', 'info');
        return;
    }

    const statusEl = document.getElementById('exportStatus');
    const resultEl = document.getElementById('exportResult');
    const progressEl = document.getElementById('exportProgress');
    const messageEl = document.getElementById('exportMessage');
    const btn = document.getElementById('exportAllBtn');

    statusEl.style.display = 'block';
    resultEl.style.display = 'none';
    progressEl.style.width = '0%';
    messageEl.textContent = '正在导出...';
    isExporting = true;
    btn.disabled = true;
    btn.style.opacity = '0.6';

    try {
        // 模拟进度
        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 80) {
                progress += Math.random() * 15;
                if (progress > 80) progress = 80;
                progressEl.style.width = progress + '%';
            }
        }, 200);

        const response = await fetch('/api/export', { method: 'POST' });
        const result = await response.json();

        clearInterval(progressInterval);

        if (result.success) {
            progressEl.style.width = '100%';
            messageEl.textContent = '导出成功！';

            resultEl.style.display = 'block';
            resultEl.innerHTML = `
                <div style="background: #d1fae5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin-top: 10px;">
                    <p style="color: #065f46; margin: 0 0 10px 0; font-weight: 600;">
                        ✓ 导出完成！
                    </p>
                    <p style="color: #065f46; margin: 0; font-size: 13px;">
                        生成文件位于: <code style="background: rgba(0,0,0,0.1); padding: 2px 6px; border-radius: 4px;">${escapeHtml(result.output_dir || 'output/')}</code>
                    </p>
                    <p style="color: #065f46; margin: 8px 0 0 0; font-size: 13px;">
                        ${result.stats ? `成功: ${result.stats.success} 个页面` : ''}
                    </p>
                </div>
            `;
            showToast('静态网站导出成功！', 'success');
        } else {
            throw new Error(result.error || '导出失败');
        }
    } catch (error) {
        console.error('导出失败:', error);
        messageEl.textContent = '导出失败: ' + error.message;

        resultEl.style.display = 'block';
        resultEl.innerHTML = `
            <div style="background: #fee2e2; border: 1px solid #ef4444; border-radius: 8px; padding: 15px; margin-top: 10px;">
                <p style="color: #991b1b; margin: 0; font-weight: 600;">
                    ✗ 导出失败
                </p>
                <p style="color: #991b1b; margin: 8px 0 0 0; font-size: 13px;">
                    ${escapeHtml(error.message)}
                </p>
                <p style="color: #991b1b; margin: 8px 0 0 0; font-size: 13px;">
                    提示: 确保已安装 jinja2 库 (pip install jinja2)
                </p>
            </div>
        `;
        showToast('导出失败: ' + error.message, 'error');
    } finally {
        isExporting = false;
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

/**
 * 下载导出 ZIP 包
 */
async function downloadExportZip() {
    if (isExporting) {
        showToast('正在导出中，请稍候...', 'info');
        return;
    }

    const btn = document.getElementById('downloadZipBtn');
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.innerHTML = '<span>⏳</span> 正在打包...';

    try {
        showToast('正在生成 ZIP 包，请稍候...', 'info');

        const response = await fetch('/api/export/download');
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '下载失败');
        }

        // 获取ZIP文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        // 创建下载链接
        const a = document.createElement('a');
        a.href = url;
        a.download = response.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1] || 'starclub-static.zip';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showToast('ZIP 包下载成功！', 'success');
    } catch (error) {
        console.error('下载失败:', error);
        showToast('下载失败: ' + error.message, 'error');
    } finally {
        isExporting = false;
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerHTML = '<span>📥</span> 下载 ZIP 包';
    }
}

/**
 * 下载 GitHub Pages 用 ZIP 包（替换内部链接）
 */
async function downloadGithubZip() {
    if (isExporting) {
        showToast('正在导出中，请稍候...', 'info');
        return;
    }

    const btn = document.getElementById('downloadGithubBtn');
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.innerHTML = '<span>⏳</span> 正在打包...';

    try {
        showToast('正在生成 GitHub Pages 包，请稍候...', 'info');

        const response = await fetch('/api/export/download-github');
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '下载失败');
        }

        // 获取ZIP文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        // 创建下载链接
        const a = document.createElement('a');
        a.href = url;
        a.download = response.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1] || 'starclub-github.zip';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showToast('GitHub Pages 包下载成功！', 'success');
    } catch (error) {
        console.error('下载失败:', error);
        showToast('下载失败: ' + error.message, 'error');
    } finally {
        isExporting = false;
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerHTML = '<span>📤</span> GitHub 发布';
    }
}

/**
 * 检查导出模块状态
 */
async function checkExportStatus() {
    try {
        const response = await fetch('/api/export/status');
        const result = await response.json();

        const exportBtn = document.getElementById('exportAllBtn');
        const downloadBtn = document.getElementById('downloadZipBtn');

        if (!result.available) {
            exportBtn.disabled = true;
            downloadBtn.disabled = true;
            exportBtn.title = '导出模块未安装: ' + (result.message || '');
            downloadBtn.title = '导出模块未安装';
        }
    } catch (error) {
        console.warn('无法获取导出状态:', error);
    }
}

// 页面加载时检查导出状态
checkExportStatus();


// ==================== 文件管理 ====================

let currentFileCategory = 'all';

/**
 * 初始化文件管理
 */
function initFileManager() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const categoryTabs = document.querySelectorAll('.category-tab');

    // 点击上传
    uploadZone.addEventListener('click', () => fileInput.click());

    // 文件选择
    fileInput.addEventListener('change', handleFileSelect);

    // 拖拽上传
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files);
        }
    });

    // 分类切换
    categoryTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            categoryTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentFileCategory = tab.dataset.category;
            loadFileList();
        });
    });

    // 加载文件列表
    loadFileList();
}

/**
 * 处理文件选择
 */
function handleFileSelect(e) {
    if (e.target.files.length) {
        handleFileUpload(e.target.files);
    }
}

/**
 * 上传文件
 */
async function handleFileUpload(files) {
    const category = document.getElementById('uploadCategory').value;
    const uploadZone = document.getElementById('uploadZone');

    if (files.length === 0) return;

    uploadZone.style.opacity = '0.6';

    let successCount = 0;
    let failCount = 0;

    for (const file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', category);

            const response = await fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                successCount++;
            } else {
                failCount++;
                console.error('上传失败:', result.error);
            }
        } catch (error) {
            failCount++;
            console.error('上传错误:', error);
        }
    }

    uploadZone.style.opacity = '1';

    if (successCount > 0) {
        showToast(`成功上传 ${successCount} 个文件`, 'success');
        loadFileList();
    }
    if (failCount > 0) {
        showToast(`${failCount} 个文件上传失败`, 'error');
    }
}

/**
 * 加载文件列表
 */
async function loadFileList() {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = '<div class="file-list-loading">加载中...</div>';

    try {
        const url = currentFileCategory === 'all'
            ? '/api/files'
            : `/api/files/${currentFileCategory}`;

        const response = await fetch(url);
        const result = await response.json();

        if (result.success && result.files.length > 0) {
            renderFileList(result.files);
        } else if (result.success) {
            fileList.innerHTML = '<div class="file-list-empty">暂无文件，上传一些文件吧</div>';
        } else {
            fileList.innerHTML = '<div class="file-list-empty">加载失败</div>';
        }
    } catch (error) {
        console.error('加载文件列表失败:', error);
        fileList.innerHTML = '<div class="file-list-empty">加载失败，请刷新重试</div>';
    }
}

/**
 * 渲染文件列表
 */
function renderFileList(files) {
    const fileList = document.getElementById('fileList');

    const categoryNames = {
        'images': '📷 图片',
        'avatars': '👤 头像',
        'documents': '📄 文档',
        'videos': '🎬 视频',
        'other': '📦 其他'
    };

    fileList.innerHTML = files.map(file => {
        const isImage = /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(file.name);
        const preview = isImage ? `<img src="../${file.path}" class="file-thumb" onerror="this.style.display='none'">` : '';
        const typeIcon = getFileIcon(file.name);

        return `
            <div class="file-item">
                <div class="file-info">
                    ${preview}
                    <div class="file-icon">${typeIcon}</div>
                    <div class="file-details">
                        <div class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
                        <div class="file-path">${escapeHtml(file.path)}</div>
                    </div>
                </div>
                <div class="file-category">${categoryNames[file.category] || file.category}</div>
                <div class="file-size">${formatFileSize(file.size)}</div>
                <div class="file-actions">
                    <button class="btn-tiny" onclick="copyFilePath('${escapeHtml(file.path)}')" title="复制路径">复制</button>
                    <button class="btn-tiny btn-edit" onclick="showRenameModal('${escapeHtml(file.path)}', '${escapeHtml(file.name)}')" title="重命名">重命名</button>
                    <button class="btn-tiny btn-delete" onclick="deleteFile('${escapeHtml(file.path)}')" title="删除">删除</button>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 获取文件图标
 */
function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'pdf': '📕',
        'doc': '📘', 'docx': '📘',
        'xls': '📗', 'xlsx': '📗',
        'ppt': '📙', 'pptx': '📙',
        'txt': '📝',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️', 'svg': '🖼️',
        'mp4': '🎬', 'webm': '🎬', 'avi': '🎬', 'mov': '🎬',
        'mp3': '🎵', 'wav': '🎵', 'ogg': '🎵',
        'zip': '📦', 'rar': '📦', '7z': '📦',
    };
    return icons[ext] || '📄';
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

/**
 * 复制文件路径
 */
function copyFilePath(path) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(path).then(() => {
            showToast('路径已复制到剪贴板', 'success');
        }).catch(() => {
            showToast('复制失败', 'error');
        });
    } else {
        const ta = document.createElement('textarea');
        ta.value = path;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            showToast('路径已复制到剪贴板', 'success');
        } catch (e) {
            showToast('复制失败', 'error');
        }
        document.body.removeChild(ta);
    }
}

/**
 * 删除文件
 */
async function deleteFile(path) {
    showConfirm('确定要删除这个文件吗？\n' + path, async () => {
    try {
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });

        const result = await response.json();

        if (result.success) {
            showToast('文件已删除', 'success');
            loadFileList();
        } else {
            throw new Error(result.error || '删除失败');
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
    });
}

// ==================== 文件重命名 ====================

let renameCurrentPath = '';

/**
 * 显示重命名模态框
 */
function showRenameModal(path, name) {
    renameCurrentPath = path;
    document.getElementById('renameOldName').value = name;
    document.getElementById('renameNewName').value = name;
    document.getElementById('renameModal').style.display = 'flex';
    // 聚焦并选中文件名（不含扩展名）
    setTimeout(() => {
        const input = document.getElementById('renameNewName');
        input.focus();
        const dotIndex = name.lastIndexOf('.');
        if (dotIndex > 0) {
            input.setSelectionRange(0, dotIndex);
        } else {
            input.select();
        }
    }, 100);
}

/**
 * 关闭重命名模态框
 */
function closeRenameModal() {
    document.getElementById('renameModal').style.display = 'none';
    renameCurrentPath = '';
}

/**
 * 确认重命名
 */
async function confirmRename() {
    const newName = document.getElementById('renameNewName').value.trim();
    if (!newName) {
        showToast('请输入新文件名', 'error');
        return;
    }
    if (!renameCurrentPath) {
        showToast('未选择文件', 'error');
        return;
    }

    try {
        const response = await fetch('/api/files/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: renameCurrentPath, newName })
        });

        const result = await response.json();
        if (result.success) {
            showToast(`已重命名为 ${result.newName}`, 'success');
            closeRenameModal();
            loadFileList();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        showToast('重命名失败: ' + error.message, 'error');
    }
}

/**
 * 在重命名弹窗中填入随机文件名
 */
function fillRandomName() {
    const input = document.getElementById('renameNewName');
    const oldName = document.getElementById('renameOldName').value;
    const ext = oldName.includes('.') ? '.' + oldName.split('.').pop() : '';
    // 生成12位随机十六进制字符串
    const random = Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, '0')).join('');
    input.value = random + ext;
    input.focus();
    input.select();
}

// 初始化文件管理
initFileManager();

// ============ 账号管理 ============

let accountsCache = [];

async function loadAccountsTable() {
    try {
        const response = await fetch('/api/admin/users');
        const result = await response.json();
        if (result.success) {
            accountsCache = result.users || [];
            renderAccountsTable();
        }
    } catch (error) {
        console.error('加载账号列表失败:', error);
    }
}

function renderAccountsTable() {
    const tbody = document.getElementById('accountsTableBody');
    if (!tbody) return;

    if (accountsCache.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;">暂无账号数据</td></tr>';
        return;
    }

    tbody.innerHTML = accountsCache.map(userId => `
        <tr>
            <td style="font-family:monospace;">${escapeHtml(userId)}</td>
            <td>${userId === 'admin' ? '<span style="color:#28a745;font-weight:600;">管理员</span>' : '<span style="color:#6c757d;">普通账号</span>'}</td>
            <td>
                ${userId === 'admin'
                    ? '<span style="color:#999;">不可删除</span>'
                    : `<button class="btn-tiny btn-delete" onclick="removeAccount('${escapeHtml(userId)}')">删除</button>`
                }
            </td>
        </tr>
    `).join('');
}

function showAddAccountModal() {
    document.getElementById('modalTitle').textContent = '添加账号';
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label for="addUserIdInput">用户ID（Nextcloud用户ID）</label>
            <input type="text" id="addUserIdInput" placeholder="请输入用户ID" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;">
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = () => {
        const userId = document.getElementById('addUserIdInput').value.trim();
        if (userId) {
            closeModal();
            addAccount(userId);
        } else {
            showToast('请输入用户ID', 'warning');
        }
    };
    openModal();
}

async function addAccount(userId) {
    try {
        const response = await fetch('/api/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const result = await response.json();
        if (result.success) {
            showToast(`已添加账号: ${userId}`, 'success');
            loadAccountsTable();
        } else {
            showToast('添加失败: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('添加失败: ' + error.message, 'error');
    }
}

async function removeAccount(userId) {
    if (!confirm(`确定要移除账号 "${userId}" 吗？移除后将无法访问管理后台。`)) {
        return;
    }
    try {
        const response = await fetch(`/api/admin/users/${encodeURIComponent(userId)}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (result.success) {
            showToast(`已移除账号: ${userId}`, 'success');
            loadAccountsTable();
        } else {
            showToast('移除失败: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('移除失败: ' + error.message, 'error');
    }
}

async function searchNextcloudUsers() {
    const query = document.getElementById('searchNextcloudInput').value.trim();
    const resultsDiv = document.getElementById('searchResults');
    const resultsList = document.getElementById('searchResultsList');

    if (!query) {
        showToast('请输入搜索关键词', 'warning');
        return;
    }

    try {
        const response = await fetch(`/api/admin/users/search?query=${encodeURIComponent(query)}`);
        const result = await response.json();
        if (result.success) {
            const users = result.users || [];
            if (users.length === 0) {
                resultsList.innerHTML = '<p style="color:#999;">未找到匹配的用户</p>';
            } else {
                resultsList.innerHTML = users.map(user => `
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#fff;border:1px solid #ddd;border-radius:6px;margin-bottom:8px;">
                        <span>
                            <strong>${escapeHtml(user.id)}</strong>
                            ${user.name ? `<span style="color:#666;margin-left:8px;">${escapeHtml(user.name)}</span>` : ''}
                        </span>
                        <button class="btn-tiny btn-primary" onclick="addAccountFromSearch('${escapeHtml(user.id)}')">+ 添加</button>
                    </div>
                `).join('');
            }
            resultsDiv.style.display = 'block';
        } else {
            showToast('搜索失败: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('搜索失败: ' + error.message, 'error');
    }
}

async function addAccountFromSearch(userId) {
    await addAccount(userId);
    document.getElementById('searchResults').style.display = 'none';
    document.getElementById('searchNextcloudInput').value = '';
}

// 搜索框回车事件
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchNextcloudInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchNextcloudUsers();
            }
        });
    }
});
