function setDrawioDarkMode(enable) {
  let elements = document.querySelectorAll(".mxgraph");
  elements.forEach(element => {
    let data = JSON.parse(element.dataset.mxgraph);
    data["dark-mode"] = enable ? "dark" : "light";
    element.dataset.mxgraph = JSON.stringify(data);
  });
}

function isPageDark() {
  return __md_get("__palette").index === 1;
}

document$.subscribe(({ body }) => {
  setDrawioDarkMode(isPageDark());
  GraphViewer.processElements()
})

document.getElementById("__palette_0").addEventListener("change", () => {
  console.log('Switched to light mode');
  setDrawioDarkMode(false);
  GraphViewer.processElements();
});

document.getElementById("__palette_1").addEventListener("change", () => {
  console.log('Switched to dark mode');
  setDrawioDarkMode(true);
  GraphViewer.processElements();
});
