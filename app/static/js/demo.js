'use strict';

const demoSteps = [...document.querySelectorAll('[data-demo-step]')];
const demoPanels = [...document.querySelectorAll('[data-demo-panel]')];
let demoIndex = 0;

function selectDemoStep(index) {
  demoIndex = index;
  demoSteps.forEach((button, position) => {
    button.classList.toggle('active', position === index);
    button.setAttribute('aria-pressed', String(position === index));
  });
  demoPanels.forEach((panel, position) => { panel.hidden = position !== index; });
  document.querySelector('.demo-outline').toggleAttribute('hidden', index !== 1);
  document.querySelector('.demo-map').hidden = index !== 2;
  document.querySelector('.demo-repair').hidden = index !== 3;
}

demoSteps.forEach((button, index) => button.addEventListener('click', () => selectDemoStep(index)));
document.getElementById('demo-next').addEventListener('click', () => selectDemoStep((demoIndex + 1) % demoSteps.length));
