// Video -> Figma  (plugin main thread)
// Receives image bytes from the UI and lays them out as a horizontal
// stack of frames, each sized to the video's native aspect ratio.

figma.showUI(__html__, { width: 400, height: 660 });

function sendPages() {
  const pages = figma.root.children.map(function (p) {
    return { id: p.id, name: p.name };
  });
  figma.ui.postMessage({
    type: "pages",
    pages: pages,
    current: figma.currentPage.id,
  });
}

sendPages();

function resolvePage(msg) {
  if (msg.newPageName) {
    const p = figma.createPage();
    p.name = msg.newPageName;
    return p;
  }
  const found = figma.root.children.filter(function (pg) {
    return pg.id === msg.pageId;
  })[0];
  return found || figma.currentPage;
}

// Find a clear spot below any existing content on the page.
function clearOrigin(page, ignore) {
  const nodes = page.children.filter(function (n) {
    return n !== ignore;
  });
  if (!nodes.length) return { x: 0, y: 0 };
  let minX = Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    minX = Math.min(minX, n.x);
    maxY = Math.max(maxY, n.y + n.height);
  }
  return { x: minX, y: maxY + 200 };
}

figma.ui.onmessage = async function (msg) {
  if (msg.type === "place") {
    try {
      await place(msg);
    } catch (e) {
      figma.ui.postMessage({
        type: "error",
        message: "Placement failed: " + (e && e.message ? e.message : e),
      });
    }
  } else if (msg.type === "cancel") {
    figma.closePlugin();
  }
};

async function place(msg) {
  const page = resolvePage(msg);
  figma.currentPage = page;

  // --- artefact scan (step 7): prior exports + duplicate of this video ---
  const prior = page.children.filter(function (n) {
    return typeof n.getPluginData === "function" && n.getPluginData("vtf") === "1";
  });
  const dup = prior.filter(function (n) {
    return n.getPluginData("vtf_url") === msg.videoUrl;
  });

  // --- build the horizontal stack ---
  const parent = figma.createFrame();
  parent.name = msg.title || "Video screenshots";
  parent.layoutMode = "HORIZONTAL";
  parent.primaryAxisSizingMode = "AUTO";
  parent.counterAxisSizingMode = "AUTO";
  parent.itemSpacing = msg.gap || 40;
  parent.paddingTop = 0;
  parent.paddingBottom = 0;
  parent.paddingLeft = 0;
  parent.paddingRight = 0;
  parent.fills = [];
  parent.clipsContent = false;
  parent.setPluginData("vtf", "1");
  parent.setPluginData("vtf_url", msg.videoUrl || "");

  let totalWidth = 0;
  for (let i = 0; i < msg.frames.length; i++) {
    const item = msg.frames[i];
    const image = figma.createImage(item.bytes);
    const size = await image.getSizeAsync();

    const f = figma.createFrame();
    f.resize(size.width, size.height);
    f.fills = [{ type: "IMAGE", scaleMode: "FILL", imageHash: image.hash }];
    f.name = item.index + " · " + item.label;
    f.setPluginData("vtf", "1");
    parent.appendChild(f);
    totalWidth += size.width + (msg.gap || 40);

    figma.ui.postMessage({
      type: "progress",
      done: i + 1,
      total: msg.frames.length,
    });
  }

  // --- space check (step 6): place in a clear region below existing art ---
  const origin = clearOrigin(page, parent);
  parent.x = origin.x;
  parent.y = origin.y;

  figma.currentPage.selection = [parent];
  figma.viewport.scrollAndZoomIntoView([parent]);

  figma.ui.postMessage({
    type: "done",
    count: msg.frames.length,
    priorExports: prior.length,
    duplicates: dup.length,
    totalWidth: Math.round(totalWidth),
    page: page.name,
  });
}
