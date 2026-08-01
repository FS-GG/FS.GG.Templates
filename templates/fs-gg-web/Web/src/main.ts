import "./site.css";
import { loadMessage } from "./api";

if (typeof document !== "undefined") {
  const target = document.querySelector<HTMLParagraphElement>("#message");
  if (target) loadMessage().then(value => target.textContent = value.message).catch(error => target.textContent = error.message);
}
