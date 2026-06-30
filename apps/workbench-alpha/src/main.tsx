import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { CaseStudy } from "./CaseStudy";
import { CoachSurface } from "./CoachSurface";
import { MomentZero } from "./MomentZero";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element not found");
}

const params = new URLSearchParams(window.location.search);
const Root =
  window.location.pathname === "/moment-zero" || params.get("moment") === "0"
    ? MomentZero
    : window.location.pathname === "/case-study"
      ? CaseStudy
    : window.location.pathname === "/workbench"
      ? App
      : CoachSurface;

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
