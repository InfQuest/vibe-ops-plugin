(function() {
  // Interactive roles that should get refs (for click/fill/interact)
  const INTERACTIVE_ROLES = new Set([
    'button', 'link', 'textbox', 'checkbox', 'radio',
    'combobox', 'listbox', 'menuitem', 'menuitemcheckbox',
    'menuitemradio', 'option', 'searchbox', 'slider',
    'spinbutton', 'switch', 'tab', 'treeitem', 'gridcell'
  ]);

  // Content roles that should get refs when named (for text extraction)
  const CONTENT_ROLES = new Set([
    // Document structure
    'heading', 'cell', 'columnheader', 'rowheader', 'listitem',
    'article', 'paragraph', 'blockquote', 'figure', 'caption',
    'img', 'definition', 'term', 'note', 'code',
    // Landmarks
    'banner', 'main', 'navigation', 'region', 'search',
    'complementary', 'contentinfo', 'form'
  ]);

  // Get computed ARIA role for an element
  function getAriaRole(element) {
    // Explicit role
    const explicitRole = element.getAttribute('role');
    if (explicitRole) {
      const roles = explicitRole.split(' ').map(r => r.trim()).filter(Boolean);
      if (roles.length > 0) return roles[0];
    }

    // Implicit role based on tag
    const tagName = element.tagName.toUpperCase();
    const implicitRoles = {
      'A': element.hasAttribute('href') ? 'link' : null,
      'BUTTON': 'button',
      'INPUT': getInputRole(element),
      'SELECT': element.hasAttribute('multiple') || element.size > 1 ? 'listbox' : 'combobox',
      'TEXTAREA': 'textbox',
      'OPTION': 'option',
    };
    return implicitRoles[tagName] || null;
  }

  function getInputRole(input) {
    const type = (input.type || 'text').toLowerCase();
    const typeToRole = {
      'button': 'button', 'submit': 'button', 'reset': 'button', 'image': 'button',
      'checkbox': 'checkbox', 'radio': 'radio',
      'range': 'slider', 'number': 'spinbutton',
      'search': 'searchbox',
      'text': 'textbox', 'email': 'textbox', 'tel': 'textbox', 'url': 'textbox', 'password': 'textbox',
    };
    return typeToRole[type] || 'textbox';
  }

  // Get accessible name for an element
  function getAccessibleName(element) {
    // aria-label
    const ariaLabel = element.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel.trim();

    // aria-labelledby
    const labelledBy = element.getAttribute('aria-labelledby');
    if (labelledBy) {
      const ids = labelledBy.split(' ').filter(Boolean);
      const names = ids.map(id => {
        const el = document.getElementById(id);
        return el ? el.textContent : '';
      }).filter(Boolean);
      if (names.length > 0) return names.join(' ').trim();
    }

    // For inputs, check labels
    if (element.labels && element.labels.length > 0) {
      return Array.from(element.labels).map(l => l.textContent).join(' ').trim();
    }

    // title attribute
    const title = element.getAttribute('title');
    if (title) return title.trim();

    // For buttons and links, use text content
    const role = getAriaRole(element);
    if (['button', 'link', 'menuitem', 'tab', 'option'].includes(role)) {
      return (element.textContent || '').trim().substring(0, 100);
    }

    // placeholder for inputs
    if (element.placeholder) return element.placeholder;

    return '';
  }

  // Check if element is visible
  function isVisible(element) {
    const style = window.getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  // Generate refs for interactive and named content elements
  // Options: { interactive: boolean } - if true, only include interactive elements
  function generateRefs(options = {}) {
    const refs = {};
    const refsList = [];
    let refCounter = 0;

    // Track role+name combinations for duplicate detection
    const roleNameCounts = new Map();  // key -> count
    const roleNameRefs = new Map();    // key -> [ref indices]

    const interactiveOnly = options.interactive === true;

    const allElements = document.querySelectorAll('*');
    for (const element of allElements) {
      const role = getAriaRole(element);
      if (!role) continue;
      if (!isVisible(element)) continue;

      const isInteractive = INTERACTIVE_ROLES.has(role);
      const isContent = CONTENT_ROLES.has(role);

      // In interactive-only mode, skip content elements
      if (interactiveOnly && !isInteractive) continue;

      // Skip if not interactive or content
      if (!isInteractive && !isContent) continue;

      const name = getAccessibleName(element);

      // Content roles only get refs when they have a name
      if (isContent && !isInteractive && !name) continue;

      const refId = 'e' + (++refCounter);

      // Track duplicates
      const key = role + ':' + (name || '');
      const nth = roleNameCounts.get(key) || 0;
      roleNameCounts.set(key, nth + 1);

      // Store ref index for later duplicate detection
      const refIndex = refsList.length;
      if (!roleNameRefs.has(key)) roleNameRefs.set(key, []);
      roleNameRefs.get(key).push(refIndex);

      refs[refId] = element;
      refsList.push({
        ref: refId,
        role: role,
        name: name,
        tagName: element.tagName.toLowerCase(),
        nth: nth,  // Will be cleaned up for non-duplicates
      });
    }

    // Remove nth from non-duplicates (keep output clean)
    for (const [_, indices] of roleNameRefs) {
      if (indices.length === 1) {
        delete refsList[indices[0]].nth;
      }
    }

    return { refs, refsList };
  }

  // Expose function
  window.__devBrowser_generateRefs = generateRefs;
})();
