import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element not found");
}

const params = new URLSearchParams(window.location.search);
const MomentZero = React.lazy(() => import("./MomentZero").then((module) => ({ default: module.MomentZero })));
const Root = window.location.pathname === "/moment-zero" || params.get("moment") === "0" ? MomentZero : App;

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <React.Suspense fallback={<div className="momentRouteLoading" aria-label="Loading Moment 0" />}>
      <Root />
    </React.Suspense>
  </React.StrictMode>
);
