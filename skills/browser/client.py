#!/usr/bin/env -S uv run --script --python 3.12
# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "playwright>=1.49.0",
#     "requests>=2.31.0",
# ]
# ///

"""
Browser automation client for Max.

Connects to the Browser Server's session-scoped API.
Requires MAX_SESSION_ID environment variable.

Usage:
    uv run client.py list
    uv run client.py create <name> [url]
    uv run client.py goto <name> <url>
    uv run client.py screenshot <name> [output_path]
    uv run client.py click <name> <selector>
    uv run client.py fill <name> <selector> <text>
    uv run client.py hover <name> <selector>
    uv run client.py keyboard <name> <key>
    uv run client.py evaluate <name> <script>
    uv run client.py text <name> <selector>
    uv run client.py snapshot <name>
    uv run client.py select-ref <name> <ref> <action> [value]
    uv run client.py wait-selector <name> <selector>
    uv run client.py wait-url <name> <url_pattern>
    uv run client.py wait-load <name>
    uv run client.py close <name>
    uv run client.py info <name>
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, Any

import requests
from playwright.sync_api import sync_playwright, Browser, Page, ElementHandle


SERVER_URL = "http://localhost:9222"


# ARIA Snapshot script - ported from dev-browser
SNAPSHOT_SCRIPT = '''
(function() {
  // Skip if already injected
  if (window.__devBrowser_getAISnapshot) return;

  // === domUtils ===
  let cacheStyle;
  let cachesCounter = 0;

  function beginDOMCaches() {
    ++cachesCounter;
    cacheStyle = cacheStyle || new Map();
  }

  function endDOMCaches() {
    if (!--cachesCounter) {
      cacheStyle = undefined;
    }
  }

  function getElementComputedStyle(element, pseudo) {
    const cache = cacheStyle;
    const cacheKey = pseudo ? undefined : element;
    if (cache && cacheKey && cache.has(cacheKey)) return cache.get(cacheKey);
    const style = element.ownerDocument && element.ownerDocument.defaultView
      ? element.ownerDocument.defaultView.getComputedStyle(element, pseudo)
      : undefined;
    if (cache && cacheKey) cache.set(cacheKey, style);
    return style;
  }

  function parentElementOrShadowHost(element) {
    if (element.parentElement) return element.parentElement;
    if (!element.parentNode) return;
    if (element.parentNode.nodeType === 11 && element.parentNode.host)
      return element.parentNode.host;
  }

  function enclosingShadowRootOrDocument(element) {
    let node = element;
    while (node.parentNode) node = node.parentNode;
    if (node.nodeType === 11 || node.nodeType === 9)
      return node;
  }

  function closestCrossShadow(element, css, scope) {
    while (element) {
      const closest = element.closest(css);
      if (scope && closest !== scope && closest?.contains(scope)) return;
      if (closest) return closest;
      element = enclosingShadowHost(element);
    }
  }

  function enclosingShadowHost(element) {
    while (element.parentElement) element = element.parentElement;
    return parentElementOrShadowHost(element);
  }

  function isElementStyleVisibilityVisible(element, style) {
    style = style || getElementComputedStyle(element);
    if (!style) return true;
    if (style.visibility !== "visible") return false;
    const detailsOrSummary = element.closest("details,summary");
    if (detailsOrSummary !== element && detailsOrSummary?.nodeName === "DETAILS" && !detailsOrSummary.open)
      return false;
    return true;
  }

  function computeBox(element) {
    const style = getElementComputedStyle(element);
    if (!style) return { visible: true, inline: false };
    const cursor = style.cursor;
    if (style.display === "contents") {
      for (let child = element.firstChild; child; child = child.nextSibling) {
        if (child.nodeType === 1 && isElementVisible(child))
          return { visible: true, inline: false, cursor };
        if (child.nodeType === 3 && isVisibleTextNode(child))
          return { visible: true, inline: true, cursor };
      }
      return { visible: false, inline: false, cursor };
    }
    if (!isElementStyleVisibilityVisible(element, style))
      return { cursor, visible: false, inline: false };
    const rect = element.getBoundingClientRect();
    return { rect, cursor, visible: rect.width > 0 && rect.height > 0, inline: style.display === "inline" };
  }

  function isElementVisible(element) {
    return computeBox(element).visible;
  }

  function isVisibleTextNode(node) {
    const range = node.ownerDocument.createRange();
    range.selectNode(node);
    const rect = range.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function elementSafeTagName(element) {
    const tagName = element.tagName;
    if (typeof tagName === "string") return tagName.toUpperCase();
    if (element instanceof HTMLFormElement) return "FORM";
    return element.tagName.toUpperCase();
  }

  function normalizeWhiteSpace(text) {
    return text.split("\\u00A0").map(chunk =>
      chunk.replace(/\\r\\n/g, "\\n").replace(/[\\u200b\\u00ad]/g, "").replace(/\\s\\s*/g, " ")
    ).join("\\u00A0").trim();
  }

  // === yaml ===
  function yamlEscapeKeyIfNeeded(str) {
    if (!yamlStringNeedsQuotes(str)) return str;
    return "'" + str.replace(/'/g, "''") + "'";
  }

  function yamlEscapeValueIfNeeded(str) {
    if (!yamlStringNeedsQuotes(str)) return str;
    return '"' + str.replace(/[\\\\"\x00-\\x1f\\x7f-\\x9f]/g, c => {
      switch (c) {
        case "\\\\": return "\\\\\\\\";
        case '"': return '\\\\"';
        case "\\b": return "\\\\b";
        case "\\f": return "\\\\f";
        case "\\n": return "\\\\n";
        case "\\r": return "\\\\r";
        case "\\t": return "\\\\t";
        default:
          const code = c.charCodeAt(0);
          return "\\\\x" + code.toString(16).padStart(2, "0");
      }
    }) + '"';
  }

  function yamlStringNeedsQuotes(str) {
    if (str.length === 0) return true;
    if (/^\\s|\\s$/.test(str)) return true;
    if (/[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\x9f]/.test(str)) return true;
    if (/^-/.test(str)) return true;
    if (/[\\n:](\\s|$)/.test(str)) return true;
    if (/\\s#/.test(str)) return true;
    if (/[\\n\\r]/.test(str)) return true;
    if (/^[&*\\],?!>|@"'#%]/.test(str)) return true;
    if (/[{}\\`]/.test(str)) return true;
    if (/^\\[/.test(str)) return true;
    if (!isNaN(Number(str)) || ["y","n","yes","no","true","false","on","off","null"].includes(str.toLowerCase())) return true;
    return false;
  }

  // === roleUtils ===
  const validRoles = ["alert","alertdialog","application","article","banner","blockquote","button","caption","cell","checkbox","code","columnheader","combobox","complementary","contentinfo","definition","deletion","dialog","directory","document","emphasis","feed","figure","form","generic","grid","gridcell","group","heading","img","insertion","link","list","listbox","listitem","log","main","mark","marquee","math","meter","menu","menubar","menuitem","menuitemcheckbox","menuitemradio","navigation","none","note","option","paragraph","presentation","progressbar","radio","radiogroup","region","row","rowgroup","rowheader","scrollbar","search","searchbox","separator","slider","spinbutton","status","strong","subscript","superscript","switch","tab","table","tablist","tabpanel","term","textbox","time","timer","toolbar","tooltip","tree","treegrid","treeitem"];

  let cacheAccessibleName;
  let cacheIsHidden;
  let cachePointerEvents;
  let ariaCachesCounter = 0;

  function beginAriaCaches() {
    beginDOMCaches();
    ++ariaCachesCounter;
    cacheAccessibleName = cacheAccessibleName || new Map();
    cacheIsHidden = cacheIsHidden || new Map();
    cachePointerEvents = cachePointerEvents || new Map();
  }

  function endAriaCaches() {
    if (!--ariaCachesCounter) {
      cacheAccessibleName = undefined;
      cacheIsHidden = undefined;
      cachePointerEvents = undefined;
    }
    endDOMCaches();
  }

  function hasExplicitAccessibleName(e) {
    return e.hasAttribute("aria-label") || e.hasAttribute("aria-labelledby");
  }

  const kAncestorPreventingLandmark = "article:not([role]), aside:not([role]), main:not([role]), nav:not([role]), section:not([role]), [role=article], [role=complementary], [role=main], [role=navigation], [role=region]";

  const kGlobalAriaAttributes = [
    ["aria-atomic", undefined],["aria-busy", undefined],["aria-controls", undefined],["aria-current", undefined],
    ["aria-describedby", undefined],["aria-details", undefined],["aria-dropeffect", undefined],["aria-flowto", undefined],
    ["aria-grabbed", undefined],["aria-hidden", undefined],["aria-keyshortcuts", undefined],
    ["aria-label", ["caption","code","deletion","emphasis","generic","insertion","paragraph","presentation","strong","subscript","superscript"]],
    ["aria-labelledby", ["caption","code","deletion","emphasis","generic","insertion","paragraph","presentation","strong","subscript","superscript"]],
    ["aria-live", undefined],["aria-owns", undefined],["aria-relevant", undefined],["aria-roledescription", ["generic"]]
  ];

  function hasGlobalAriaAttribute(element, forRole) {
    return kGlobalAriaAttributes.some(([attr, prohibited]) => !prohibited?.includes(forRole || "") && element.hasAttribute(attr));
  }

  function hasTabIndex(element) {
    return !Number.isNaN(Number(String(element.getAttribute("tabindex"))));
  }

  function isFocusable(element) {
    return !isNativelyDisabled(element) && (isNativelyFocusable(element) || hasTabIndex(element));
  }

  function isNativelyFocusable(element) {
    const tagName = elementSafeTagName(element);
    if (["BUTTON","DETAILS","SELECT","TEXTAREA"].includes(tagName)) return true;
    if (tagName === "A" || tagName === "AREA") return element.hasAttribute("href");
    if (tagName === "INPUT") return !element.hidden;
    return false;
  }

  function isNativelyDisabled(element) {
    const isNativeFormControl = ["BUTTON","INPUT","SELECT","TEXTAREA","OPTION","OPTGROUP"].includes(elementSafeTagName(element));
    return isNativeFormControl && (element.hasAttribute("disabled") || belongsToDisabledFieldSet(element));
  }

  function belongsToDisabledFieldSet(element) {
    const fieldSetElement = element?.closest("FIELDSET[DISABLED]");
    if (!fieldSetElement) return false;
    const legendElement = fieldSetElement.querySelector(":scope > LEGEND");
    return !legendElement || !legendElement.contains(element);
  }

  const inputTypeToRole = {button:"button",checkbox:"checkbox",image:"button",number:"spinbutton",radio:"radio",range:"slider",reset:"button",submit:"button"};

  function getIdRefs(element, ref) {
    if (!ref) return [];
    const root = enclosingShadowRootOrDocument(element);
    if (!root) return [];
    try {
      const ids = ref.split(" ").filter(id => !!id);
      const result = [];
      for (const id of ids) {
        const firstElement = root.querySelector("#" + CSS.escape(id));
        if (firstElement && !result.includes(firstElement)) result.push(firstElement);
      }
      return result;
    } catch { return []; }
  }

  const kImplicitRoleByTagName = {
    A: e => e.hasAttribute("href") ? "link" : null,
    AREA: e => e.hasAttribute("href") ? "link" : null,
    ARTICLE: () => "article", ASIDE: () => "complementary", BLOCKQUOTE: () => "blockquote", BUTTON: () => "button",
    CAPTION: () => "caption", CODE: () => "code", DATALIST: () => "listbox", DD: () => "definition",
    DEL: () => "deletion", DETAILS: () => "group", DFN: () => "term", DIALOG: () => "dialog", DT: () => "term",
    EM: () => "emphasis", FIELDSET: () => "group", FIGURE: () => "figure",
    FOOTER: e => closestCrossShadow(e, kAncestorPreventingLandmark) ? null : "contentinfo",
    FORM: e => hasExplicitAccessibleName(e) ? "form" : null,
    H1: () => "heading", H2: () => "heading", H3: () => "heading", H4: () => "heading", H5: () => "heading", H6: () => "heading",
    HEADER: e => closestCrossShadow(e, kAncestorPreventingLandmark) ? null : "banner",
    HR: () => "separator", HTML: () => "document",
    IMG: e => e.getAttribute("alt") === "" && !e.getAttribute("title") && !hasGlobalAriaAttribute(e) && !hasTabIndex(e) ? "presentation" : "img",
    INPUT: e => {
      const type = e.type.toLowerCase();
      if (type === "search") return e.hasAttribute("list") ? "combobox" : "searchbox";
      if (["email","tel","text","url",""].includes(type)) {
        const list = getIdRefs(e, e.getAttribute("list"))[0];
        return list && elementSafeTagName(list) === "DATALIST" ? "combobox" : "textbox";
      }
      if (type === "hidden") return null;
      if (type === "file") return "button";
      return inputTypeToRole[type] || "textbox";
    },
    INS: () => "insertion", LI: () => "listitem", MAIN: () => "main", MARK: () => "mark", MATH: () => "math",
    MENU: () => "list", METER: () => "meter", NAV: () => "navigation", OL: () => "list", OPTGROUP: () => "group",
    OPTION: () => "option", OUTPUT: () => "status", P: () => "paragraph", PROGRESS: () => "progressbar",
    SEARCH: () => "search", SECTION: e => hasExplicitAccessibleName(e) ? "region" : null,
    SELECT: e => e.hasAttribute("multiple") || e.size > 1 ? "listbox" : "combobox",
    STRONG: () => "strong", SUB: () => "subscript", SUP: () => "superscript", SVG: () => "img",
    TABLE: () => "table", TBODY: () => "rowgroup",
    TD: e => { const table = closestCrossShadow(e, "table"); const role = table ? getExplicitAriaRole(table) : ""; return role === "grid" || role === "treegrid" ? "gridcell" : "cell"; },
    TEXTAREA: () => "textbox", TFOOT: () => "rowgroup",
    TH: e => { const scope = e.getAttribute("scope"); if (scope === "col" || scope === "colgroup") return "columnheader"; if (scope === "row" || scope === "rowgroup") return "rowheader"; return "columnheader"; },
    THEAD: () => "rowgroup", TIME: () => "time", TR: () => "row", UL: () => "list"
  };

  function getExplicitAriaRole(element) {
    const roles = (element.getAttribute("role") || "").split(" ").map(role => role.trim());
    return roles.find(role => validRoles.includes(role)) || null;
  }

  function getImplicitAriaRole(element) {
    const fn = kImplicitRoleByTagName[elementSafeTagName(element)];
    return fn ? fn(element) : null;
  }

  function hasPresentationConflictResolution(element, role) {
    return hasGlobalAriaAttribute(element, role) || isFocusable(element);
  }

  function getAriaRole(element) {
    const explicitRole = getExplicitAriaRole(element);
    if (!explicitRole) return getImplicitAriaRole(element);
    if (explicitRole === "none" || explicitRole === "presentation") {
      const implicitRole = getImplicitAriaRole(element);
      if (hasPresentationConflictResolution(element, implicitRole)) return implicitRole;
    }
    return explicitRole;
  }

  function getAriaBoolean(attr) {
    return attr === null ? undefined : attr.toLowerCase() === "true";
  }

  function isElementIgnoredForAria(element) {
    return ["STYLE","SCRIPT","NOSCRIPT","TEMPLATE"].includes(elementSafeTagName(element));
  }

  function isElementHiddenForAria(element) {
    if (isElementIgnoredForAria(element)) return true;
    const style = getElementComputedStyle(element);
    const isSlot = element.nodeName === "SLOT";
    if (style?.display === "contents" && !isSlot) {
      for (let child = element.firstChild; child; child = child.nextSibling) {
        if (child.nodeType === 1 && !isElementHiddenForAria(child)) return false;
        if (child.nodeType === 3 && isVisibleTextNode(child)) return false;
      }
      return true;
    }
    const isOptionInsideSelect = element.nodeName === "OPTION" && !!element.closest("select");
    if (!isOptionInsideSelect && !isSlot && !isElementStyleVisibilityVisible(element, style)) return true;
    return belongsToDisplayNoneOrAriaHiddenOrNonSlotted(element);
  }

  function belongsToDisplayNoneOrAriaHiddenOrNonSlotted(element) {
    let hidden = cacheIsHidden?.get(element);
    if (hidden === undefined) {
      hidden = false;
      if (element.parentElement && element.parentElement.shadowRoot && !element.assignedSlot) hidden = true;
      if (!hidden) {
        const style = getElementComputedStyle(element);
        hidden = !style || style.display === "none" || getAriaBoolean(element.getAttribute("aria-hidden")) === true;
      }
      if (!hidden) {
        const parent = parentElementOrShadowHost(element);
        if (parent) hidden = belongsToDisplayNoneOrAriaHiddenOrNonSlotted(parent);
      }
      cacheIsHidden?.set(element, hidden);
    }
    return hidden;
  }

  function getAriaLabelledByElements(element) {
    const ref = element.getAttribute("aria-labelledby");
    if (ref === null) return null;
    const refs = getIdRefs(element, ref);
    return refs.length ? refs : null;
  }

  function getElementAccessibleName(element, includeHidden) {
    let accessibleName = cacheAccessibleName?.get(element);
    if (accessibleName === undefined) {
      accessibleName = "";
      const elementProhibitsNaming = ["caption","code","definition","deletion","emphasis","generic","insertion","mark","paragraph","presentation","strong","subscript","suggestion","superscript","term","time"].includes(getAriaRole(element) || "");
      if (!elementProhibitsNaming) {
        accessibleName = normalizeWhiteSpace(getTextAlternativeInternal(element, { includeHidden, visitedElements: new Set(), embeddedInTargetElement: "self" }));
      }
      cacheAccessibleName?.set(element, accessibleName);
    }
    return accessibleName;
  }

  function getTextAlternativeInternal(element, options) {
    if (options.visitedElements.has(element)) return "";
    const childOptions = { ...options, embeddedInTargetElement: options.embeddedInTargetElement === "self" ? "descendant" : options.embeddedInTargetElement };

    if (!options.includeHidden) {
      const isEmbeddedInHiddenReferenceTraversal = !!options.embeddedInLabelledBy?.hidden || !!options.embeddedInLabel?.hidden;
      if (isElementIgnoredForAria(element) || (!isEmbeddedInHiddenReferenceTraversal && isElementHiddenForAria(element))) {
        options.visitedElements.add(element);
        return "";
      }
    }

    const labelledBy = getAriaLabelledByElements(element);
    if (!options.embeddedInLabelledBy) {
      const accessibleName = (labelledBy || []).map(ref => getTextAlternativeInternal(ref, { ...options, embeddedInLabelledBy: { element: ref, hidden: isElementHiddenForAria(ref) }, embeddedInTargetElement: undefined, embeddedInLabel: undefined })).join(" ");
      if (accessibleName) return accessibleName;
    }

    const role = getAriaRole(element) || "";
    const tagName = elementSafeTagName(element);

    const ariaLabel = element.getAttribute("aria-label") || "";
    if (ariaLabel.trim()) { options.visitedElements.add(element); return ariaLabel; }

    if (!["presentation","none"].includes(role)) {
      if (tagName === "INPUT" && ["button","submit","reset"].includes(element.type)) {
        options.visitedElements.add(element);
        const value = element.value || "";
        if (value.trim()) return value;
        if (element.type === "submit") return "Submit";
        if (element.type === "reset") return "Reset";
        return element.getAttribute("title") || "";
      }
      if (tagName === "INPUT" && element.type === "image") {
        options.visitedElements.add(element);
        const alt = element.getAttribute("alt") || "";
        if (alt.trim()) return alt;
        const title = element.getAttribute("title") || "";
        if (title.trim()) return title;
        return "Submit";
      }
      if (tagName === "IMG") {
        options.visitedElements.add(element);
        const alt = element.getAttribute("alt") || "";
        if (alt.trim()) return alt;
        return element.getAttribute("title") || "";
      }
      if (!labelledBy && ["BUTTON","INPUT","TEXTAREA","SELECT"].includes(tagName)) {
        const labels = element.labels;
        if (labels?.length) {
          options.visitedElements.add(element);
          return [...labels].map(label => getTextAlternativeInternal(label, { ...options, embeddedInLabel: { element: label, hidden: isElementHiddenForAria(label) }, embeddedInLabelledBy: undefined, embeddedInTargetElement: undefined })).filter(name => !!name).join(" ");
        }
      }
    }

    const allowsNameFromContent = ["button","cell","checkbox","columnheader","gridcell","heading","link","menuitem","menuitemcheckbox","menuitemradio","option","radio","row","rowheader","switch","tab","tooltip","treeitem"].includes(role);
    if (allowsNameFromContent || !!options.embeddedInLabelledBy || !!options.embeddedInLabel) {
      options.visitedElements.add(element);
      const accessibleName = innerAccumulatedElementText(element, childOptions);
      const maybeTrimmedAccessibleName = options.embeddedInTargetElement === "self" ? accessibleName.trim() : accessibleName;
      if (maybeTrimmedAccessibleName) return accessibleName;
    }

    if (!["presentation","none"].includes(role) || tagName === "IFRAME") {
      options.visitedElements.add(element);
      const title = element.getAttribute("title") || "";
      if (title.trim()) return title;
    }

    options.visitedElements.add(element);
    return "";
  }

  function innerAccumulatedElementText(element, options) {
    const tokens = [];
    const visit = (node, skipSlotted) => {
      if (skipSlotted && node.assignedSlot) return;
      if (node.nodeType === 1) {
        const display = getElementComputedStyle(node)?.display || "inline";
        let token = getTextAlternativeInternal(node, options);
        if (display !== "inline" || node.nodeName === "BR") token = " " + token + " ";
        tokens.push(token);
      } else if (node.nodeType === 3) {
        tokens.push(node.textContent || "");
      }
    };
    const assignedNodes = element.nodeName === "SLOT" ? element.assignedNodes() : [];
    if (assignedNodes.length) {
      for (const child of assignedNodes) visit(child, false);
    } else {
      for (let child = element.firstChild; child; child = child.nextSibling) visit(child, true);
      if (element.shadowRoot) {
        for (let child = element.shadowRoot.firstChild; child; child = child.nextSibling) visit(child, true);
      }
    }
    return tokens.join("");
  }

  const kAriaCheckedRoles = ["checkbox","menuitemcheckbox","option","radio","switch","menuitemradio","treeitem"];
  function getAriaChecked(element) {
    const tagName = elementSafeTagName(element);
    if (tagName === "INPUT" && element.indeterminate) return "mixed";
    if (tagName === "INPUT" && ["checkbox","radio"].includes(element.type)) return element.checked;
    if (kAriaCheckedRoles.includes(getAriaRole(element) || "")) {
      const checked = element.getAttribute("aria-checked");
      if (checked === "true") return true;
      if (checked === "mixed") return "mixed";
      return false;
    }
    return false;
  }

  const kAriaDisabledRoles = ["application","button","composite","gridcell","group","input","link","menuitem","scrollbar","separator","tab","checkbox","columnheader","combobox","grid","listbox","menu","menubar","menuitemcheckbox","menuitemradio","option","radio","radiogroup","row","rowheader","searchbox","select","slider","spinbutton","switch","tablist","textbox","toolbar","tree","treegrid","treeitem"];
  function getAriaDisabled(element) {
    return isNativelyDisabled(element) || hasExplicitAriaDisabled(element);
  }
  function hasExplicitAriaDisabled(element, isAncestor) {
    if (!element) return false;
    if (isAncestor || kAriaDisabledRoles.includes(getAriaRole(element) || "")) {
      const attribute = (element.getAttribute("aria-disabled") || "").toLowerCase();
      if (attribute === "true") return true;
      if (attribute === "false") return false;
      return hasExplicitAriaDisabled(parentElementOrShadowHost(element), true);
    }
    return false;
  }

  const kAriaExpandedRoles = ["application","button","checkbox","combobox","gridcell","link","listbox","menuitem","row","rowheader","tab","treeitem","columnheader","menuitemcheckbox","menuitemradio","switch"];
  function getAriaExpanded(element) {
    if (elementSafeTagName(element) === "DETAILS") return element.open;
    if (kAriaExpandedRoles.includes(getAriaRole(element) || "")) {
      const expanded = element.getAttribute("aria-expanded");
      if (expanded === null) return undefined;
      if (expanded === "true") return true;
      return false;
    }
    return undefined;
  }

  const kAriaLevelRoles = ["heading","listitem","row","treeitem"];
  function getAriaLevel(element) {
    const native = {H1:1,H2:2,H3:3,H4:4,H5:5,H6:6}[elementSafeTagName(element)];
    if (native) return native;
    if (kAriaLevelRoles.includes(getAriaRole(element) || "")) {
      const attr = element.getAttribute("aria-level");
      const value = attr === null ? Number.NaN : Number(attr);
      if (Number.isInteger(value) && value >= 1) return value;
    }
    return 0;
  }

  const kAriaPressedRoles = ["button"];
  function getAriaPressed(element) {
    if (kAriaPressedRoles.includes(getAriaRole(element) || "")) {
      const pressed = element.getAttribute("aria-pressed");
      if (pressed === "true") return true;
      if (pressed === "mixed") return "mixed";
    }
    return false;
  }

  const kAriaSelectedRoles = ["gridcell","option","row","tab","rowheader","columnheader","treeitem"];
  function getAriaSelected(element) {
    if (elementSafeTagName(element) === "OPTION") return element.selected;
    if (kAriaSelectedRoles.includes(getAriaRole(element) || "")) return getAriaBoolean(element.getAttribute("aria-selected")) === true;
    return false;
  }

  function receivesPointerEvents(element) {
    const cache = cachePointerEvents;
    let e = element;
    let result;
    const parents = [];
    for (; e; e = parentElementOrShadowHost(e)) {
      const cached = cache?.get(e);
      if (cached !== undefined) { result = cached; break; }
      parents.push(e);
      const style = getElementComputedStyle(e);
      if (!style) { result = true; break; }
      const value = style.pointerEvents;
      if (value) { result = value !== "none"; break; }
    }
    if (result === undefined) result = true;
    for (const parent of parents) cache?.set(parent, result);
    return result;
  }

  function getCSSContent(element, pseudo) {
    const style = getElementComputedStyle(element, pseudo);
    if (!style) return undefined;
    const contentValue = style.content;
    if (!contentValue || contentValue === "none" || contentValue === "normal") return undefined;
    if (style.display === "none" || style.visibility === "hidden") return undefined;
    const match = contentValue.match(/^"(.*)"$/);
    if (match) {
      const content = match[1].replace(/\\\\"/g, '"');
      if (pseudo) {
        const display = style.display || "inline";
        if (display !== "inline") return " " + content + " ";
      }
      return content;
    }
    return undefined;
  }

  // === ariaSnapshot ===
  let lastRef = 0;

  function generateAriaTree(rootElement) {
    const options = { visibility: "ariaOrVisible", refs: "interactable", refPrefix: "", includeGenericRole: true, renderActive: true, renderCursorPointer: true };
    const visited = new Set();
    const snapshot = {
      root: { role: "fragment", name: "", children: [], element: rootElement, props: {}, box: computeBox(rootElement), receivesPointerEvents: true },
      elements: new Map(),
      refs: new Map(),
      iframeRefs: []
    };

    const visit = (ariaNode, node, parentElementVisible) => {
      if (visited.has(node)) return;
      visited.add(node);
      if (node.nodeType === Node.TEXT_NODE && node.nodeValue) {
        if (!parentElementVisible) return;
        const text = node.nodeValue;
        if (ariaNode.role !== "textbox" && text) ariaNode.children.push(node.nodeValue || "");
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      const element = node;
      const isElementVisibleForAria = !isElementHiddenForAria(element);
      let visible = isElementVisibleForAria;
      if (options.visibility === "ariaOrVisible") visible = isElementVisibleForAria || isElementVisible(element);
      if (options.visibility === "ariaAndVisible") visible = isElementVisibleForAria && isElementVisible(element);
      if (options.visibility === "aria" && !visible) return;
      const ariaChildren = [];
      if (element.hasAttribute("aria-owns")) {
        const ids = element.getAttribute("aria-owns").split(/\\s+/);
        for (const id of ids) {
          const ownedElement = rootElement.ownerDocument.getElementById(id);
          if (ownedElement) ariaChildren.push(ownedElement);
        }
      }
      const childAriaNode = visible ? toAriaNode(element, options) : null;
      if (childAriaNode) {
        if (childAriaNode.ref) {
          snapshot.elements.set(childAriaNode.ref, element);
          snapshot.refs.set(element, childAriaNode.ref);
          if (childAriaNode.role === "iframe") snapshot.iframeRefs.push(childAriaNode.ref);
        }
        ariaNode.children.push(childAriaNode);
      }
      processElement(childAriaNode || ariaNode, element, ariaChildren, visible);
    };

    function processElement(ariaNode, element, ariaChildren, parentElementVisible) {
      const display = getElementComputedStyle(element)?.display || "inline";
      const treatAsBlock = display !== "inline" || element.nodeName === "BR" ? " " : "";
      if (treatAsBlock) ariaNode.children.push(treatAsBlock);
      ariaNode.children.push(getCSSContent(element, "::before") || "");
      const assignedNodes = element.nodeName === "SLOT" ? element.assignedNodes() : [];
      if (assignedNodes.length) {
        for (const child of assignedNodes) visit(ariaNode, child, parentElementVisible);
      } else {
        for (let child = element.firstChild; child; child = child.nextSibling) {
          if (!child.assignedSlot) visit(ariaNode, child, parentElementVisible);
        }
        if (element.shadowRoot) {
          for (let child = element.shadowRoot.firstChild; child; child = child.nextSibling) visit(ariaNode, child, parentElementVisible);
        }
      }
      for (const child of ariaChildren) visit(ariaNode, child, parentElementVisible);
      ariaNode.children.push(getCSSContent(element, "::after") || "");
      if (treatAsBlock) ariaNode.children.push(treatAsBlock);
      if (ariaNode.children.length === 1 && ariaNode.name === ariaNode.children[0]) ariaNode.children = [];
      if (ariaNode.role === "link" && element.hasAttribute("href")) ariaNode.props["url"] = element.getAttribute("href");
      if (ariaNode.role === "textbox" && element.hasAttribute("placeholder") && element.getAttribute("placeholder") !== ariaNode.name) ariaNode.props["placeholder"] = element.getAttribute("placeholder");
    }

    beginAriaCaches();
    try { visit(snapshot.root, rootElement, true); }
    finally { endAriaCaches(); }
    normalizeStringChildren(snapshot.root);
    normalizeGenericRoles(snapshot.root);
    return snapshot;
  }

  function computeAriaRef(ariaNode, options) {
    if (options.refs === "none") return;
    if (options.refs === "interactable" && (!ariaNode.box.visible || !ariaNode.receivesPointerEvents)) return;
    let ariaRef = ariaNode.element._ariaRef;
    if (!ariaRef || ariaRef.role !== ariaNode.role || ariaRef.name !== ariaNode.name) {
      ariaRef = { role: ariaNode.role, name: ariaNode.name, ref: (options.refPrefix || "") + "e" + (++lastRef) };
      ariaNode.element._ariaRef = ariaRef;
    }
    ariaNode.ref = ariaRef.ref;
  }

  function toAriaNode(element, options) {
    const active = element.ownerDocument.activeElement === element;
    if (element.nodeName === "IFRAME") {
      const ariaNode = { role: "iframe", name: "", children: [], props: {}, element, box: computeBox(element), receivesPointerEvents: true, active };
      computeAriaRef(ariaNode, options);
      return ariaNode;
    }
    const defaultRole = options.includeGenericRole ? "generic" : null;
    const role = getAriaRole(element) || defaultRole;
    if (!role || role === "presentation" || role === "none") return null;
    const name = normalizeWhiteSpace(getElementAccessibleName(element, false) || "");
    const receivesPointerEventsValue = receivesPointerEvents(element);
    const box = computeBox(element);
    if (role === "generic" && box.inline && element.childNodes.length === 1 && element.childNodes[0].nodeType === Node.TEXT_NODE) return null;
    const result = { role, name, children: [], props: {}, element, box, receivesPointerEvents: receivesPointerEventsValue, active };
    computeAriaRef(result, options);
    if (kAriaCheckedRoles.includes(role)) result.checked = getAriaChecked(element);
    if (kAriaDisabledRoles.includes(role)) result.disabled = getAriaDisabled(element);
    if (kAriaExpandedRoles.includes(role)) result.expanded = getAriaExpanded(element);
    if (kAriaLevelRoles.includes(role)) result.level = getAriaLevel(element);
    if (kAriaPressedRoles.includes(role)) result.pressed = getAriaPressed(element);
    if (kAriaSelectedRoles.includes(role)) result.selected = getAriaSelected(element);
    if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
      if (element.type !== "checkbox" && element.type !== "radio" && element.type !== "file") result.children = [element.value];
    }
    return result;
  }

  function normalizeGenericRoles(node) {
    const normalizeChildren = (node) => {
      const result = [];
      for (const child of node.children || []) {
        if (typeof child === "string") { result.push(child); continue; }
        const normalized = normalizeChildren(child);
        result.push(...normalized);
      }
      const removeSelf = node.role === "generic" && !node.name && result.length <= 1 && result.every(c => typeof c !== "string" && !!c.ref);
      if (removeSelf) return result;
      node.children = result;
      return [node];
    };
    normalizeChildren(node);
  }

  function normalizeStringChildren(rootA11yNode) {
    const flushChildren = (buffer, normalizedChildren) => {
      if (!buffer.length) return;
      const text = normalizeWhiteSpace(buffer.join(""));
      if (text) normalizedChildren.push(text);
      buffer.length = 0;
    };
    const visit = (ariaNode) => {
      const normalizedChildren = [];
      const buffer = [];
      for (const child of ariaNode.children || []) {
        if (typeof child === "string") { buffer.push(child); }
        else { flushChildren(buffer, normalizedChildren); visit(child); normalizedChildren.push(child); }
      }
      flushChildren(buffer, normalizedChildren);
      ariaNode.children = normalizedChildren.length ? normalizedChildren : [];
      if (ariaNode.children.length === 1 && ariaNode.children[0] === ariaNode.name) ariaNode.children = [];
    };
    visit(rootA11yNode);
  }

  function hasPointerCursor(ariaNode) { return ariaNode.box.cursor === "pointer"; }

  function renderAriaTree(ariaSnapshot) {
    const options = { visibility: "ariaOrVisible", refs: "interactable", refPrefix: "", includeGenericRole: true, renderActive: true, renderCursorPointer: true };
    const lines = [];
    let nodesToRender = ariaSnapshot.root.role === "fragment" ? ariaSnapshot.root.children : [ariaSnapshot.root];

    const visitText = (text, indent) => {
      const escaped = yamlEscapeValueIfNeeded(text);
      if (escaped) lines.push(indent + "- text: " + escaped);
    };

    const createKey = (ariaNode, renderCursorPointer) => {
      let key = ariaNode.role;
      if (ariaNode.name && ariaNode.name.length <= 900) {
        const name = ariaNode.name;
        if (name) {
          const stringifiedName = name.startsWith("/") && name.endsWith("/") ? name : JSON.stringify(name);
          key += " " + stringifiedName;
        }
      }
      if (ariaNode.checked === "mixed") key += " [checked=mixed]";
      if (ariaNode.checked === true) key += " [checked]";
      if (ariaNode.disabled) key += " [disabled]";
      if (ariaNode.expanded) key += " [expanded]";
      if (ariaNode.active && options.renderActive) key += " [active]";
      if (ariaNode.level) key += " [level=" + ariaNode.level + "]";
      if (ariaNode.pressed === "mixed") key += " [pressed=mixed]";
      if (ariaNode.pressed === true) key += " [pressed]";
      if (ariaNode.selected === true) key += " [selected]";
      if (ariaNode.ref) {
        key += " [ref=" + ariaNode.ref + "]";
        if (renderCursorPointer && hasPointerCursor(ariaNode)) key += " [cursor=pointer]";
      }
      return key;
    };

    const getSingleInlinedTextChild = (ariaNode) => {
      return ariaNode?.children.length === 1 && typeof ariaNode.children[0] === "string" && !Object.keys(ariaNode.props).length ? ariaNode.children[0] : undefined;
    };

    const visit = (ariaNode, indent, renderCursorPointer) => {
      const escapedKey = indent + "- " + yamlEscapeKeyIfNeeded(createKey(ariaNode, renderCursorPointer));
      const singleInlinedTextChild = getSingleInlinedTextChild(ariaNode);
      if (!ariaNode.children.length && !Object.keys(ariaNode.props).length) {
        lines.push(escapedKey);
      } else if (singleInlinedTextChild !== undefined) {
        lines.push(escapedKey + ": " + yamlEscapeValueIfNeeded(singleInlinedTextChild));
      } else {
        lines.push(escapedKey + ":");
        for (const [name, value] of Object.entries(ariaNode.props)) lines.push(indent + "  - /" + name + ": " + yamlEscapeValueIfNeeded(value));
        const childIndent = indent + "  ";
        const inCursorPointer = !!ariaNode.ref && renderCursorPointer && hasPointerCursor(ariaNode);
        for (const child of ariaNode.children) {
          if (typeof child === "string") visitText(child, childIndent);
          else visit(child, childIndent, renderCursorPointer && !inCursorPointer);
        }
      }
    };

    for (const nodeToRender of nodesToRender) {
      if (typeof nodeToRender === "string") visitText(nodeToRender, "");
      else visit(nodeToRender, "", !!options.renderCursorPointer);
    }
    return lines.join("\\n");
  }

  function getAISnapshot() {
    const snapshot = generateAriaTree(document.body);
    const refsObject = {};
    for (const [ref, element] of snapshot.elements) refsObject[ref] = element;
    window.__devBrowserRefs = refsObject;
    return renderAriaTree(snapshot);
  }

  function selectSnapshotRef(ref) {
    const refs = window.__devBrowserRefs;
    if (!refs) throw new Error("No snapshot refs found. Call getAISnapshot first.");
    const element = refs[ref];
    if (!element) throw new Error('Ref "' + ref + '" not found. Available refs: ' + Object.keys(refs).join(", "));
    return element;
  }

  // Expose main functions
  window.__devBrowser_getAISnapshot = getAISnapshot;
  window.__devBrowser_selectSnapshotRef = selectSnapshotRef;
})();
'''


@dataclass
class PageInfo:
    """Page information"""
    name: str
    target_id: str
    ws_endpoint: str
    title: str
    url: str


@dataclass
class WaitForPageLoadResult:
    """Result of waiting for page load"""
    success: bool
    ready_state: str
    pending_requests: int
    wait_time_ms: int
    timed_out: bool


class BrowserClient:
    """Session-scoped browser client for Max."""

    def __init__(self, session_id: Optional[str] = None):
        """Initialize client with session ID from env or parameter."""
        self.session_id = session_id or os.environ.get("MAX_SESSION_ID")
        if not self.session_id:
            raise RuntimeError(
                "MAX_SESSION_ID environment variable is required.\n"
                "Make sure you're running this from within Max."
            )

        self.base_url = f"{SERVER_URL}/sessions/{self.session_id}"
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._browser_ws_endpoint: Optional[str] = None
        self._page_cache: dict[str, Page] = {}

    def _check_server(self) -> bool:
        """Check if browser server is running."""
        try:
            resp = requests.get(SERVER_URL, timeout=2)
            return resp.ok
        except requests.RequestException:
            return False

    def _ensure_browser_connected(self) -> Browser:
        """Ensure we have a browser connection, connecting if necessary."""
        if self._browser and self._browser.is_connected():
            return self._browser

        # Get browser-level wsEndpoint from server root
        resp = requests.get(SERVER_URL, timeout=5)
        if not resp.ok:
            raise RuntimeError(f"Failed to get server info: {resp.status_code}")

        server_info = resp.json()
        ws_endpoint = server_info.get("wsEndpoint")
        if not ws_endpoint:
            raise RuntimeError("Server did not return wsEndpoint")

        # Start playwright if needed
        if not self._playwright:
            self._playwright = sync_playwright().start()

        # Connect to browser
        self._browser = self._playwright.chromium.connect_over_cdp(ws_endpoint)
        self._browser_ws_endpoint = ws_endpoint
        return self._browser

    def _find_page_by_target_id(self, browser: Browser, target_id: str) -> Optional[Page]:
        """Find a page by its CDP targetId."""
        for context in browser.contexts:
            for page in context.pages:
                try:
                    # Create CDP session to get target info
                    cdp_session = context.new_cdp_session(page)
                    try:
                        result = cdp_session.send("Target.getTargetInfo")
                        page_target_id = result.get("targetInfo", {}).get("targetId")
                        if page_target_id == target_id:
                            return page
                    finally:
                        try:
                            cdp_session.detach()
                        except Exception:
                            pass  # Ignore detach errors
                except Exception as e:
                    # Ignore errors for closed pages
                    msg = str(e)
                    if "Target closed" not in msg and "Session closed" not in msg:
                        print(f"Warning: Error checking page target: {msg}", file=sys.stderr)
        return None

    def list_pages(self) -> list[PageInfo]:
        """List all pages in current session"""
        resp = requests.get(f"{self.base_url}/pages")
        if not resp.ok:
            if resp.status_code == 404:
                return []  # Session doesn't exist yet
            raise RuntimeError(f"Failed to list pages: {resp.status_code}")

        data = resp.json()
        return [
            PageInfo(
                name=p["name"],
                target_id=p["targetId"],
                ws_endpoint=p["wsEndpoint"],
                title=p.get("title", ""),
                url=p.get("url", ""),
            )
            for p in data.get("pages", [])
        ]

    def create_page(self, name: str, url: Optional[str] = None) -> PageInfo:
        """Create a new page for current session"""
        payload = {"name": name}
        if url:
            payload["url"] = url

        resp = requests.post(
            f"{self.base_url}/pages",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if not resp.ok:
            error = resp.json().get("error", f"HTTP {resp.status_code}")
            raise RuntimeError(f"Failed to create page: {error}")

        data = resp.json()
        return PageInfo(
            name=data["name"],
            target_id=data["targetId"],
            ws_endpoint=data["wsEndpoint"],
            title="",
            url=data.get("url", ""),
        )

    def get_page_info(self, name: str) -> PageInfo:
        """Get page details"""
        resp = requests.get(f"{self.base_url}/pages/{name}")
        if not resp.ok:
            raise RuntimeError(f"Page '{name}' not found")

        data = resp.json()
        return PageInfo(
            name=data["name"],
            target_id=data["targetId"],
            ws_endpoint=data["wsEndpoint"],
            title=data.get("title", ""),
            url=data.get("url", ""),
        )

    def close_page(self, name: str) -> bool:
        """Close a page"""
        resp = requests.delete(f"{self.base_url}/pages/{name}")

        # Clear from cache
        if name in self._page_cache:
            del self._page_cache[name]

        return resp.ok

    def get_playwright_page(self, name: str) -> Page:
        """Get Playwright Page object"""
        # Check cache first
        if name in self._page_cache:
            cached = self._page_cache[name]
            if not cached.is_closed():
                return cached
            # Remove stale cache entry
            del self._page_cache[name]

        # Get page info (contains targetId)
        page_info = self.get_page_info(name)

        # Connect to browser (reuses existing connection)
        browser = self._ensure_browser_connected()

        # Find page by targetId
        page = self._find_page_by_target_id(browser, page_info.target_id)
        if not page:
            # Debug: list available pages
            all_pages = []
            for ctx in browser.contexts:
                for p in ctx.pages:
                    all_pages.append(p.url[:50] if p.url else "(blank)")
            raise RuntimeError(
                f"Page '{name}' (targetId={page_info.target_id}) not found in browser.\n"
                f"Available pages: {all_pages}"
            )

        self._page_cache[name] = page
        return page

    def get_or_create_page(self, name: str, url: Optional[str] = None) -> Page:
        """Get or create page (idempotent operation)"""
        try:
            return self.get_playwright_page(name)
        except RuntimeError:
            # Page doesn't exist, create it
            self.create_page(name, url)
            return self.get_playwright_page(name)

    def disconnect(self):
        """Disconnect all connections"""
        self._page_cache.clear()
        self._browser = None
        self._browser_ws_endpoint = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    # === New Features ===

    def get_ai_snapshot(self, name: str) -> str:
        """Get AI-friendly ARIA snapshot for a page.
        Returns YAML format with refs like [ref=e1], [ref=e2].
        """
        page = self.get_playwright_page(name)

        # Inject snapshot script and call getAISnapshot
        snapshot = page.evaluate(f"""() => {{
            {SNAPSHOT_SCRIPT}
            return window.__devBrowser_getAISnapshot();
        }}""")

        return snapshot

    def select_snapshot_ref(self, name: str, ref: str) -> ElementHandle:
        """Get an element handle by its ref from the last getAISnapshot call."""
        page = self.get_playwright_page(name)

        element_handle = page.evaluate_handle(f"""(refId) => {{
            const refs = window.__devBrowserRefs;
            if (!refs) {{
                throw new Error("No snapshot refs found. Call getAISnapshot first.");
            }}
            const element = refs[refId];
            if (!element) {{
                throw new Error('Ref "' + refId + '" not found. Available refs: ' + Object.keys(refs).join(", "));
            }}
            return element;
        }}""", ref)

        element = element_handle.as_element()
        if not element:
            raise RuntimeError(f"Ref '{ref}' did not resolve to an element")

        return element

    def wait_for_page_load(
        self,
        name: str,
        timeout: int = 10000,
        poll_interval: int = 50,
        minimum_wait: int = 100,
        wait_for_network_idle: bool = True
    ) -> WaitForPageLoadResult:
        """Wait for a page to finish loading using document.readyState and performance API."""
        page = self.get_playwright_page(name)

        start_time = time.time() * 1000  # ms
        last_state = None

        # Wait minimum time first
        if minimum_wait > 0:
            time.sleep(minimum_wait / 1000)

        # Poll until ready or timeout
        while (time.time() * 1000 - start_time) < timeout:
            try:
                last_state = page.evaluate("""() => {
                    const perf = performance;
                    const doc = document;
                    const now = perf.now();
                    const resources = perf.getEntriesByType("resource");
                    const pending = [];

                    const adPatterns = [
                        "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
                        "google-analytics.com", "facebook.net", "connect.facebook.net",
                        "analytics", "ads", "tracking", "pixel", "hotjar.com", "clarity.ms",
                        "mixpanel.com", "segment.com", "newrelic.com", "nr-data.net",
                        "/tracker/", "/collector/", "/beacon/", "/telemetry/", "/log/",
                        "/events/", "/track.", "/metrics/"
                    ];

                    const nonCriticalTypes = ["img", "image", "icon", "font"];

                    for (const entry of resources) {
                        if (entry.responseEnd === 0) {
                            const url = entry.name;
                            const isAd = adPatterns.some(pattern => url.includes(pattern));
                            if (isAd) continue;
                            if (url.startsWith("data:") || url.length > 500) continue;

                            const loadingDuration = now - entry.startTime;
                            if (loadingDuration > 10000) continue;

                            const resourceType = entry.initiatorType || "unknown";
                            if (nonCriticalTypes.includes(resourceType) && loadingDuration > 3000) continue;

                            const isImageUrl = /\\.(jpg|jpeg|png|gif|webp|svg|ico)(\\?|$)/i.test(url);
                            if (isImageUrl && loadingDuration > 3000) continue;

                            pending.push({
                                url: url,
                                loadingDurationMs: Math.round(loadingDuration),
                                resourceType: resourceType
                            });
                        }
                    }

                    return {
                        documentReadyState: doc.readyState,
                        documentLoading: doc.readyState !== "complete",
                        pendingRequests: pending
                    };
                }""")

                document_ready = last_state["documentReadyState"] == "complete"
                network_idle = not wait_for_network_idle or len(last_state["pendingRequests"]) == 0

                if document_ready and network_idle:
                    return WaitForPageLoadResult(
                        success=True,
                        ready_state=last_state["documentReadyState"],
                        pending_requests=len(last_state["pendingRequests"]),
                        wait_time_ms=int(time.time() * 1000 - start_time),
                        timed_out=False
                    )
            except Exception:
                # Page may be navigating, continue polling
                pass

            time.sleep(poll_interval / 1000)

        # Timeout reached
        return WaitForPageLoadResult(
            success=False,
            ready_state=last_state["documentReadyState"] if last_state else "unknown",
            pending_requests=len(last_state["pendingRequests"]) if last_state else 0,
            wait_time_ms=int(time.time() * 1000 - start_time),
            timed_out=True
        )


# === CLI Commands ===

def cmd_list(client: BrowserClient, args):
    """List all pages in current session."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        print("Please make sure Max is open.")
        return 1

    pages = client.list_pages()
    if not pages:
        print("No pages in current session.")
        return 0

    print(f"Pages in session ({len(pages)}):")
    for p in pages:
        print(f"  - {p.name}: {p.title or p.url or '(empty)'}")
    return 0


def cmd_create(client: BrowserClient, args):
    """Create a new page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page_info = client.create_page(args.name, args.url)
        print(f"Created page: {page_info.name}")
        print(f"  targetId: {page_info.target_id}")
        if args.url:
            print(f"  url: {args.url}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1


def cmd_goto(client: BrowserClient, args):
    """Navigate a page to URL."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_or_create_page(args.name, args.url)
        if page.url != args.url:
            page.goto(args.url)
        print(f"Navigated to: {args.url}")
        print(f"Title: {page.title()}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_screenshot(client: BrowserClient, args):
    """Take a screenshot of a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        output_path = args.output or f"{args.name}.png"
        page.screenshot(path=output_path)
        print(f"Screenshot saved to: {output_path}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_click(client: BrowserClient, args):
    """Click an element on a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.click(args.selector)
        print(f"Clicked: {args.selector}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_fill(client: BrowserClient, args):
    """Fill an input element with text."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.fill(args.selector, args.text)
        print(f"Filled '{args.selector}' with: {args.text}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_hover(client: BrowserClient, args):
    """Hover over an element."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.hover(args.selector)
        print(f"Hovered: {args.selector}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_keyboard(client: BrowserClient, args):
    """Press a keyboard key."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        page.keyboard.press(args.key)
        print(f"Pressed key: {args.key}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_evaluate(client: BrowserClient, args):
    """Execute JavaScript on a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        result = page.evaluate(args.script)
        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_text(client: BrowserClient, args):
    """Get text content of an element."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        text = page.text_content(args.selector)
        print(text or "(empty)")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_snapshot(client: BrowserClient, args):
    """Get AI snapshot of a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        snapshot = client.get_ai_snapshot(args.name)
        print(snapshot)
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_select_ref(client: BrowserClient, args):
    """Select element by ref and perform action."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        element = client.select_snapshot_ref(args.name, args.ref)
        action = args.action.lower()

        if action == "click":
            element.click()
            print(f"Clicked element ref: {args.ref}")
        elif action == "fill":
            if not args.value:
                print("Error: fill action requires a value")
                return 1
            element.fill(args.value)
            print(f"Filled element ref: {args.ref}")
        elif action == "hover":
            element.hover()
            print(f"Hovered element ref: {args.ref}")
        elif action == "text":
            text = element.text_content()
            print(text or "(empty)")
        else:
            print(f"Error: Unknown action '{action}'. Supported: click, fill, hover, text")
            return 1

        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_selector(client: BrowserClient, args):
    """Wait for a selector to appear."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        timeout = args.timeout or 30000
        page.wait_for_selector(args.selector, timeout=timeout)
        print(f"Selector found: {args.selector}")
        return 0
    except Exception as e:
        print(f"Error: Timeout waiting for selector '{args.selector}': {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_url(client: BrowserClient, args):
    """Wait for URL to match pattern."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        page = client.get_playwright_page(args.name)
        timeout = args.timeout or 30000
        page.wait_for_url(args.url_pattern, timeout=timeout)
        print(f"URL matched: {page.url}")
        return 0
    except Exception as e:
        print(f"Error: Timeout waiting for URL '{args.url_pattern}': {e}")
        return 1
    finally:
        client.disconnect()


def cmd_wait_load(client: BrowserClient, args):
    """Wait for page to fully load."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        timeout = args.timeout or 10000
        result = client.wait_for_page_load(args.name, timeout=timeout)

        if result.success:
            print(f"Page loaded successfully")
            print(f"  Ready state: {result.ready_state}")
            print(f"  Wait time: {result.wait_time_ms}ms")
        else:
            print(f"Page load timed out")
            print(f"  Ready state: {result.ready_state}")
            print(f"  Pending requests: {result.pending_requests}")
            print(f"  Wait time: {result.wait_time_ms}ms")
            return 1

        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1
    finally:
        client.disconnect()


def cmd_close(client: BrowserClient, args):
    """Close a page."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    if client.close_page(args.name):
        print(f"Closed page: {args.name}")
        return 0
    else:
        print(f"Error: Page '{args.name}' not found")
        return 1


def cmd_info(client: BrowserClient, args):
    """Get page information."""
    if not client._check_server():
        print("Error: Browser server is not running.")
        return 1

    try:
        info = client.get_page_info(args.name)
        print(f"Page: {info.name}")
        print(f"  Title: {info.title}")
        print(f"  URL: {info.url}")
        print(f"  Target ID: {info.target_id}")
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Browser automation client for Max"
    )
    parser.add_argument(
        "--session-id",
        help="Session ID (defaults to MAX_SESSION_ID env var)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list
    subparsers.add_parser("list", help="List all pages in current session")

    # create
    p_create = subparsers.add_parser("create", help="Create a new page")
    p_create.add_argument("name", help="Page name")
    p_create.add_argument("url", nargs="?", help="Initial URL")

    # goto
    p_goto = subparsers.add_parser("goto", help="Navigate a page to URL")
    p_goto.add_argument("name", help="Page name")
    p_goto.add_argument("url", help="URL to navigate to")

    # screenshot
    p_screenshot = subparsers.add_parser("screenshot", help="Take a screenshot")
    p_screenshot.add_argument("name", help="Page name")
    p_screenshot.add_argument("output", nargs="?", help="Output file path")

    # click
    p_click = subparsers.add_parser("click", help="Click an element")
    p_click.add_argument("name", help="Page name")
    p_click.add_argument("selector", help="CSS selector")

    # fill
    p_fill = subparsers.add_parser("fill", help="Fill an input element")
    p_fill.add_argument("name", help="Page name")
    p_fill.add_argument("selector", help="CSS selector")
    p_fill.add_argument("text", help="Text to fill")

    # hover
    p_hover = subparsers.add_parser("hover", help="Hover over an element")
    p_hover.add_argument("name", help="Page name")
    p_hover.add_argument("selector", help="CSS selector")

    # keyboard
    p_keyboard = subparsers.add_parser("keyboard", help="Press a keyboard key")
    p_keyboard.add_argument("name", help="Page name")
    p_keyboard.add_argument("key", help="Key to press (e.g., Enter, Tab, Escape)")

    # evaluate
    p_evaluate = subparsers.add_parser("evaluate", help="Execute JavaScript")
    p_evaluate.add_argument("name", help="Page name")
    p_evaluate.add_argument("script", help="JavaScript code to execute")

    # text
    p_text = subparsers.add_parser("text", help="Get text content of element")
    p_text.add_argument("name", help="Page name")
    p_text.add_argument("selector", help="CSS selector")

    # snapshot
    p_snapshot = subparsers.add_parser("snapshot", help="Get AI snapshot (ARIA tree)")
    p_snapshot.add_argument("name", help="Page name")

    # select-ref
    p_select_ref = subparsers.add_parser("select-ref", help="Select element by ref and perform action")
    p_select_ref.add_argument("name", help="Page name")
    p_select_ref.add_argument("ref", help="Element ref (e.g., e1, e2)")
    p_select_ref.add_argument("action", help="Action: click, fill, hover, text")
    p_select_ref.add_argument("value", nargs="?", help="Value for fill action")

    # wait-selector
    p_wait_selector = subparsers.add_parser("wait-selector", help="Wait for selector")
    p_wait_selector.add_argument("name", help="Page name")
    p_wait_selector.add_argument("selector", help="CSS selector")
    p_wait_selector.add_argument("--timeout", type=int, help="Timeout in ms (default: 30000)")

    # wait-url
    p_wait_url = subparsers.add_parser("wait-url", help="Wait for URL to match")
    p_wait_url.add_argument("name", help="Page name")
    p_wait_url.add_argument("url_pattern", help="URL pattern (string or regex)")
    p_wait_url.add_argument("--timeout", type=int, help="Timeout in ms (default: 30000)")

    # wait-load
    p_wait_load = subparsers.add_parser("wait-load", help="Wait for page to fully load")
    p_wait_load.add_argument("name", help="Page name")
    p_wait_load.add_argument("--timeout", type=int, help="Timeout in ms (default: 10000)")

    # close
    p_close = subparsers.add_parser("close", help="Close a page")
    p_close.add_argument("name", help="Page name")

    # info
    p_info = subparsers.add_parser("info", help="Get page information")
    p_info.add_argument("name", help="Page name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        client = BrowserClient(args.session_id)
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    commands = {
        "list": cmd_list,
        "create": cmd_create,
        "goto": cmd_goto,
        "screenshot": cmd_screenshot,
        "click": cmd_click,
        "fill": cmd_fill,
        "hover": cmd_hover,
        "keyboard": cmd_keyboard,
        "evaluate": cmd_evaluate,
        "text": cmd_text,
        "snapshot": cmd_snapshot,
        "select-ref": cmd_select_ref,
        "wait-selector": cmd_wait_selector,
        "wait-url": cmd_wait_url,
        "wait-load": cmd_wait_load,
        "close": cmd_close,
        "info": cmd_info,
    }

    return commands[args.command](client, args)


if __name__ == "__main__":
    sys.exit(main())
