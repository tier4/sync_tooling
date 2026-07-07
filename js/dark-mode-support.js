function setDrawioDarkMode(enable) {
  let elements = document.querySelectorAll(".mxgraph");
  elements.forEach(element => {
    let data = JSON.parse(element.dataset.mxgraph);
    data["dark-mode"] = enable ? "dark" : "light";
    element.dataset.mxgraph = JSON.stringify(data);
  });
}

function setEchartsDarkMode(enable) {
  if (typeof chart !== "undefined") {
    chart.setTheme(enable ? 'dark' : 'default');
  }
}

function setDarkMode(enable) {
  setDrawioDarkMode(enable);
  setEchartsDarkMode(enable);
}

function isPageDark() {
  return __md_get("__palette").index === 1;
}

function reloadGraph() {
  console.debug("Reloading graph");
  const has_graph_viewer = typeof GraphViewer !== "undefined";
  has_graph_viewer && GraphViewer.processElements() || console.debug("GraphViewer not yet loaded");
}

document$.subscribe(({ body }) => {
  setDarkMode(isPageDark());
  reloadGraph();
})

document.getElementById("__palette_0").addEventListener("change", () => {
  console.log('Switched to light mode');
  setDarkMode(false);
  reloadGraph();
});

document.getElementById("__palette_1").addEventListener("change", () => {
  console.log('Switched to dark mode');
  setDarkMode(true);
  reloadGraph();
});
