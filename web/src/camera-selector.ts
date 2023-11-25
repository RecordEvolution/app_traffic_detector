import { LitElement, html, css } from 'lit';
import { state, customElement } from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import '@material/web/select/outlined-select.js'
import '@material/web/select/select-option.js'

@customElement('camera-selector')
export class CameraSelector extends LitElement {

  @state()
  private camList: any[] = [];

  selector?: HTMLSelectElement
  constructor() {
    super()
  }
  async firstUpdated() {

      this.selector = this.shadowRoot?.getElementById('selector') as HTMLSelectElement
      this.camList = await fetch('http://localhost:1100/cameras', {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      }).then(res => res.json())

      console.log('CAMLIST', this.camList)
  }

  async selectCamera() {
    const value = this.selector?.value
    console.log('selected', value)
    const payload = {selected: value}
    await fetch('http://localhost:1100/cameras/select', {
      method: 'POST',
      headers: {
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload), 
    })
  }

  static styles = css`
    :host {
      display: block;
    }
    :root {
      --md-filled-select-text-field-container-shape: 0px;
      --md-filled-select-text-field-container-color: #f7faf9;
      --md-filled-select-text-field-input-text-color: #005353;
      --md-filled-select-text-field-input-text-font: system-ui;
    }

    md-filled-select::part(menu) {
      --md-menu-container-color: #f4fbfa;
      --md-menu-container-shape: 0px;
    }
  `;

  render() {
    return html`
      <md-outlined-select id="selector" @change=${this.selectCamera}>
        ${repeat(this.camList, c => c.path, c => html`
        <md-select-option selected value="${c.path}">
          <div slot="headline">${c.name}</div>
        </md-select-option>
        `)}
      </md-outlined-select>
    `;
  }
}
