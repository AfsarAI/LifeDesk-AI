import {
  Children,
  cloneElement,
  createContext,
  Fragment,
  isValidElement,
  useContext,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { Check, Copy, ExternalLink, ImageOff } from "lucide-react";

const BR_SENTINEL = "\uE000LIFEDESK_BR\uE000";
const InsidePreContext = createContext(false);

const SAFE_IMAGE_SRC_RE =
  /^(https?:\/\/|\/(?!\/)|data:image\/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=]+$)/i;
const SAFE_LINK_HREF_RE = /^(https?:\/\/|mailto:|\/(?!\/)|#)/i;
const TABLE_SEPARATOR_RE = /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*(?::?-{3,}:?)?\s*$/;

/**
 * Normalize assistant Markdown before parsing without enabling raw HTML rendering:
 * - Preserves fenced code blocks and inline code spans verbatim.
 * - Converts HTML `<br>` / `<br/>` tags outside code into an internal sentinel token.
 * - Inserts a blank line before GFM tables immediately following prose lines.
 */
function preprocessMarkdown(raw: string): string {
  if (!raw) return "";

  const normalizedNewlines = raw.replace(/\r\n?/g, "\n");
  // Tokenize fenced code blocks (``` or ~~~) and inline code spans (`...`) so code stays literal.
  const segments = normalizedNewlines.split(
    /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)/g
  );

  const processed = segments
    .map((segment, index) => {
      if (index % 2 === 1) {
        return segment;
      }
      return segment.replace(/<br\s*\/?>/gi, BR_SENTINEL);
    })
    .join("");

  const lines = processed.split("\n");
  const out: string[] = [];
  let inFence = false;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    if (/^(?:```|~~~)/.test(trimmed)) {
      inFence = !inFence;
      out.push(line);
      continue;
    }

    if (
      !inFence &&
      i > 0 &&
      i + 1 < lines.length &&
      line.includes("|") &&
      TABLE_SEPARATOR_RE.test(lines[i + 1]) &&
      out[out.length - 1]?.trim() !== "" &&
      !out[out.length - 1]?.includes("|")
    ) {
      out.push("");
    }

    out.push(line);
  }

  return out.join("\n");
}

function renderWithBreaks(children: ReactNode): ReactNode {
  return Children.map(children, (child, idx) => {
    if (typeof child === "string") {
      if (!child.includes(BR_SENTINEL)) {
        return child;
      }
      const parts = child.split(BR_SENTINEL);
      return (
        <Fragment key={`br-frag-${idx}`}>
          {parts.map((part, pIdx) => (
            <Fragment key={`br-part-${pIdx}`}>
              {part}
              {pIdx < parts.length - 1 && <br />}
            </Fragment>
          ))}
        </Fragment>
      );
    }

    if (isValidElement<{ children?: ReactNode }>(child)) {
      if (child.type === "code" || child.type === "pre") {
        return child;
      }
      if (child.props.children !== undefined) {
        return cloneElement(child, {
          key: child.key ?? `el-${idx}`,
          children: renderWithBreaks(child.props.children),
        });
      }
    }

    return child;
  });
}

function extractText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(extractText).join("");
  }
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return extractText(node.props.children);
  }
  return "";
}

function extractCodeMetadata(children: ReactNode): {
  language: string;
  rawCode: string;
} {
  const firstChild = Children.toArray(children)[0];
  let language = "code";

  if (isValidElement<{ className?: string; children?: ReactNode }>(firstChild)) {
    const className = firstChild.props.className || "";
    const match = className.match(/language-([a-zA-Z0-9_+-]+)/);
    if (match?.[1]) {
      language = match[1];
    }
  }

  const rawCode = extractText(children).replace(/\n$/, "");
  return { language, rawCode };
}

function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const { language, rawCode } = useMemo(() => extractCodeMetadata(children), [children]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(rawCode);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/90 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/90 px-3.5 py-1.5">
        <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-slate-400">
          {language}
        </span>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white"
          aria-label={copied ? "Copied" : "Copy code"}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-emerald-300">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <InsidePreContext.Provider value={true}>
        <pre className="overflow-x-auto px-3.5 py-3 font-mono text-[12.5px] leading-relaxed text-slate-100">
          {children}
        </pre>
      </InsidePreContext.Provider>
    </div>
  );
}

function InlineOrBlockCode({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  const inPre = useContext(InsidePreContext);
  if (inPre) {
    return <code className={className}>{children}</code>;
  }
  return (
    <code className="rounded-md bg-slate-800/95 px-1.5 py-0.5 font-mono text-[12.5px] text-indigo-200 ring-1 ring-slate-700/70">
      {children}
    </code>
  );
}

function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const [failed, setFailed] = useState(false);
  const cleanSrc = (src || "").trim();
  const isSafe = SAFE_IMAGE_SRC_RE.test(cleanSrc);

  if (!cleanSrc || !isSafe || failed) {
    return (
      <div className="my-3 flex items-center gap-2.5 rounded-xl border border-slate-700/80 bg-slate-950/70 px-3.5 py-2.5 text-xs text-slate-400">
        <ImageOff className="h-4 w-4 shrink-0 text-slate-500" />
        <div className="min-w-0">
          <p className="font-medium text-slate-300">{alt || "Image unavailable"}</p>
          {cleanSrc && isSafe && (
            <p className="truncate font-mono text-[11px] text-slate-500">{cleanSrc}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <figure className="my-3">
      <img
        src={cleanSrc}
        alt={alt || "Attachment"}
        loading="lazy"
        onError={() => setFailed(true)}
        className="max-h-80 w-auto max-w-full rounded-xl border border-slate-700/80 bg-slate-950/60 object-contain shadow-sm"
      />
      {alt && (
        <figcaption className="mt-1.5 text-xs text-slate-400">{alt}</figcaption>
      )}
    </figure>
  );
}

const MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => (
    <h1 className="mt-4 mb-2 border-b border-slate-800 pb-1.5 text-lg font-semibold tracking-tight text-white first:mt-0">
      {renderWithBreaks(children)}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 mb-2 border-b border-slate-800/70 pb-1 text-base font-semibold tracking-tight text-white first:mt-0">
      {renderWithBreaks(children)}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-sm font-semibold text-slate-100 first:mt-0">
      {renderWithBreaks(children)}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-2.5 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300 first:mt-0">
      {renderWithBreaks(children)}
    </h4>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-relaxed text-slate-100 first:mt-0 last:mb-0">
      {renderWithBreaks(children)}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-slate-200">{children}</em>,
  del: ({ children }) => (
    <del className="text-slate-400 line-through">{children}</del>
  ),
  a: ({ href, children }) => {
    const cleanHref = (href || "").trim();
    if (!cleanHref || !SAFE_LINK_HREF_RE.test(cleanHref)) {
      return <span className="text-slate-300">{children}</span>;
    }
    const isExternal = /^https?:\/\//i.test(cleanHref);
    return (
      <a
        href={cleanHref}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
        className="inline-flex items-center gap-1 font-medium text-indigo-400 underline decoration-indigo-400/50 underline-offset-2 transition hover:text-indigo-300"
      >
        <span>{children}</span>
        {isExternal && <ExternalLink className="inline h-3 w-3 shrink-0 opacity-75" />}
      </a>
    );
  },
  ul: ({ children }) => (
    <ul className="my-2 ml-5 list-disc space-y-1 text-slate-100 marker:text-indigo-400 first:mt-0 last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 ml-5 list-decimal space-y-1 text-slate-100 marker:text-indigo-400 first:mt-0 last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="pl-0.5 leading-relaxed">{renderWithBreaks(children)}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 rounded-r-lg border-l-2 border-indigo-400/75 bg-slate-800/45 py-2 pr-3.5 pl-3.5 text-slate-300 italic">
      {renderWithBreaks(children)}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-slate-800" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-950/65 shadow-sm">
      <table className="w-full border-collapse text-left text-sm">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-slate-700/80 bg-slate-800/85 text-xs font-semibold uppercase tracking-wider text-slate-200">
      {children}
    </thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-slate-800/80">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="transition-colors even:bg-slate-900/40 hover:bg-slate-800/40">
      {children}
    </tr>
  ),
  th: ({ children }) => (
    <th className="px-3.5 py-2.5 text-left text-xs font-semibold tracking-wider text-slate-200">
      {renderWithBreaks(children)}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3.5 py-2.5 align-top text-sm leading-relaxed text-slate-200">
      {renderWithBreaks(children)}
    </td>
  ),
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  code: ({ className, children }) => (
    <InlineOrBlockCode className={className}>{children}</InlineOrBlockCode>
  ),
  img: ({ src, alt }) => <MarkdownImage src={src} alt={alt} />,
  input: ({ type, checked, ...rest }) => {
    if (type === "checkbox") {
      return (
        <input
          type="checkbox"
          checked={Boolean(checked)}
          readOnly
          className="mr-1.5 h-3.5 w-3.5 rounded border-slate-600 bg-slate-800 align-middle accent-indigo-500"
        />
      );
    }
    return <input type={type} {...rest} />;
  },
};

interface MarkdownMessageProps {
  content: string;
}

/**
 * Renders assistant Markdown responses (GFM tables, headings, lists, blockquotes,
 * copyable syntax-highlighted code blocks, and responsive safe images) without raw HTML.
 */
export function MarkdownMessage({ content }: MarkdownMessageProps): ReactElement {
  const prepared = useMemo(() => preprocessMarkdown(content), [content]);

  return (
    <div className="markdown-message min-w-0 break-words text-sm text-slate-100">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { ignoreMissing: true }]]}
        components={MARKDOWN_COMPONENTS}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
