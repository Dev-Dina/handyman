"""Builds the /widget.js loader script served to host pages.

The loader reads data-widget-id (and optional data-api-base-url /
data-widget-url) from the embedding <script> tag, injects an iframe,
and wires a postMessage listener so the widget can resize the iframe
when the user collapses or expands the chat panel.
"""

from __future__ import annotations

WIDGET_APP_PATH: str = "/widget-app/"

_LOADER_TEMPLATE: str = """\
(function () {
  'use strict';
  var script = document.currentScript;
  if (!script) return;

  var widgetId = script.getAttribute('data-widget-id') || '';
  var apiBase = script.getAttribute('data-api-base-url') || window.location.origin;
  var widgetAppPath = script.getAttribute('data-widget-url') || (apiBase + '__WIDGET_APP_PATH__');

  var src = widgetAppPath
    + '?widget_id=' + encodeURIComponent(widgetId)
    + '&api_base=' + encodeURIComponent(apiBase);

  var iframe = document.createElement('iframe');
  iframe.src = src;
  iframe.setAttribute('frameborder', '0');
  iframe.setAttribute('scrolling', 'no');
  iframe.setAttribute('allow', 'microphone');
  iframe.setAttribute('title', 'Chat widget');
  iframe.style.cssText = [
    'position:fixed',
    'bottom:20px',
    'right:20px',
    'border:none',
    'z-index:2147483647',
    'width:64px',
    'height:64px',
    'border-radius:50%',
    'overflow:hidden',
    'background:transparent',
  ].join(';');

  window.addEventListener('message', function (event) {
    if (!event.data || event.data.type !== 'handyman-widget-resize') return;
    if (event.source !== iframe.contentWindow) return;
    if (event.data.expanded) {
      iframe.style.width = '380px';
      iframe.style.height = '600px';
      iframe.style.borderRadius = '12px';
    } else {
      iframe.style.width = '64px';
      iframe.style.height = '64px';
      iframe.style.borderRadius = '50%';
    }
  });

  function mount() {
    if (document.body) {
      document.body.appendChild(iframe);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
"""


def build_loader_script() -> str:
    return _LOADER_TEMPLATE.replace("__WIDGET_APP_PATH__", WIDGET_APP_PATH)
