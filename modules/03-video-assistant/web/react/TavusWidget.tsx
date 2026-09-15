"use client";

import { createElement, useEffect } from "react";

type TavusWidgetProps = {
  deploymentId: string;
  greeting?: string;
  context?: string;
  memoryStore?: string;
};

const SCRIPT_ID = "tavus-widget-script";

export function TavusWidget({ deploymentId, greeting, context, memoryStore }: TavusWidgetProps) {
  useEffect(() => {
    if (document.getElementById(SCRIPT_ID)) return;
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = "https://unpkg.com/@tavus/widget";
    script.async = true;
    document.head.appendChild(script);
  }, []);

  return createElement("tavus-widget", {
    "deployment-id": deploymentId,
    ...(greeting ? { "custom-greeting": greeting } : {}),
    ...(context ? { "conversational-context": context } : {}),
    ...(memoryStore ? { "memory-stores": memoryStore } : {})
  });
}

