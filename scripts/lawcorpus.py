#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lawcorpus 查询脚本（WorkBuddy 技能版，替代原 dsh 插件的 lawcorpus_* 工具）。

用法:
  python scripts/lawcorpus.py status [--journal 中国法学] [--verbose]
  python scripts/lawcorpus.py frame --topic 数据可携权 [--journal 法学研究] [--genre 教义学] [--limit 5]
  python scripts/lawcorpus.py match --abstract "……" [--title "……"] [--keywords "词1,词2"] [--journal 中国法学] [--limit 5]
  python scripts/lawcorpus.py profile [--journal 中外法学] [--yearFrom 2024] [--yearTo 2026] [--genre 实证研究] [--topic 关键词]
  python scripts/lawcorpus.py export [--format csv|jsonl|markdown] [--journal ...] [--yearFrom ...] [--yearTo ...] [--outFile out.csv] [--includeAbstract]

数据: data/*.jsonl，一行一条论文题录，字段:
  id/journal/year/issue/title/authors/abstract/keywords/outline/discipline/pages/startPage
语料为题录层（无全文）。genre/discipline 为规则抽取，仅供参考。
"""
import argparse, json, re, sys, os, collections

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

STOP = set("的了和是在我有就不到不之与及等对为以于中从一个上也没其这那们来出可所为而或且因由并各该其于关于基于视域下研究分析思考".split()) | set("的了和是在有就不都之与及等对为以于中从一个上也其这那们来出可所为而或且因由并各该")

def load(journal=None, yearFrom=None, yearTo=None):
    arts = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(DATA_DIR, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                a = json.loads(line)
                if journal and a.get("journal") != journal:
                    continue
                if yearFrom and (a.get("year") or 0) < yearFrom:
                    continue
                if yearTo and (a.get("year") or 9999) > yearTo:
                    continue
                arts.append(a)
    return arts

def tokens(text):
    text = re.sub(r"[\s\dA-Za-z，。、《》〈〉「」“”‘’：:；;！!？?（）()【】\[\]—…·\-]+", " ", text or "")
    toks = set()
    for w in text.split():
        if len(w) >= 2:
            toks.add(w)
        for n in (2, 3, 4):
            for i in range(len(w) - n + 1):
                g = w[i:i + n]
                if g not in STOP:
                    toks.add(g)
    return toks

def cmd_status(args):
    arts = load(journal=args.journal)
    by = collections.Counter((a["journal"], a["year"]) for a in arts)
    journals = sorted({a["journal"] for a in arts})
    years = sorted({a["year"] for a in arts})
    print(f"总篇数: {len(arts)}（含笔谈/编者按）")
    print(f"覆盖期刊({len(journals)}): {' / '.join(journals)}")
    print(f"年份范围: {min(years) if years else '-'}–{max(years) if years else '-'}")
    for j in journals:
        row = [f"{j}"]
        tot = 0
        for y in years:
            n = by.get((j, y), 0)
            tot += n
            row.append(f"{y}:{n}")
        row.append(f"合计:{tot}")
        print("  " + "  ".join(row))
    std = [a for a in arts if a.get("authors")]
    if std:
        full = sum(1 for a in std if a.get("abstract") and a.get("keywords") and a.get("outline"))
        print(f"标准论文摘要/关键词/目录三者齐全率: {full}/{len(std)} = {full*100//len(std)}%")
    if args.verbose:
        for a in arts:
            if not a.get("abstract") or not a.get("outline"):
                print(f"  [不完整] {a['journal']} {a['year']}({a.get('issue')}) {a.get('title')}")

def cmd_frame(args):
    arts = load(journal=args.journal)
    if args.genre:
        arts = [a for a in arts if a.get("discipline") == args.genre]
    q = tokens(args.topic)
    scored = []
    for a in arts:
        hay = tokens(" ".join([a.get("title") or "", a.get("abstract") or "", " ".join(a.get("keywords") or [])]))
        s = len(q & hay) + 3 * sum(1 for t in q if t in (a.get("title") or ""))
        if s > 0:
            scored.append((s, a))
    scored.sort(key=lambda x: -x[0])
    kw = collections.Counter()
    for _, a in scored[:20]:
        for k in a.get("keywords") or []:
            kw[k] += 1
    print(f"选题「{args.topic}」命中 {len(scored)} 篇，以下为主要框架卡（前 {args.limit} 篇）：\n")
    for s, a in scored[:args.limit]:
        print(f"● {a['journal']} {a['year']}年第{a.get('issue')}期 | 相关度 {s}")
        print(f"  题名: {a.get('title')}")
        print(f"  作者: {'、'.join(a.get('authors') or []) or '—'}")
        print(f"  关键词: {'、'.join(a.get('keywords') or []) or '—'}")
        ab = (a.get("abstract") or "").strip()
        print(f"  摘要: {ab[:200]}{'…' if len(ab) > 200 else ''}")
        if a.get("outline"):
            print("  目录骨架:")
            for h in a["outline"][:14]:
                print(f"    - {h}")
        print()
    if kw:
        print("高频关键词: " + "、".join(k for k, _ in kw.most_common(15)))

def cmd_match(args):
    arts = load(journal=args.journal)
    qtext = " ".join([args.title or "", args.abstract or "", args.keywords or ""])
    q = tokens(qtext)
    if not q:
        print("查询为空，请提供 --abstract 或 --title。")
        return
    scored = []
    for a in arts:
        hay = tokens(" ".join([a.get("title") or "", a.get("abstract") or "", " ".join(a.get("keywords") or [])]))
        inter = q & hay
        scored.append((len(inter) / max(len(q), 1), len(inter), a))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    print(f"与语料库比对结果（分数=查询词元覆盖率，仅供粗略参考，不代表语义相似度或录用概率）：\n")
    for cov, n, a in scored[:args.limit]:
        print(f"● 覆盖 {cov*100:.0f}%（命中 {n} 词元）| {a['journal']} {a['year']}年第{a.get('issue')}期")
        print(f"  题名: {a.get('title')}")
        print(f"  关键词: {'、'.join(a.get('keywords') or []) or '—'}")
        if a.get("outline"):
            print("  目录骨架: " + " / ".join(a["outline"][:6]))
        print()

def cmd_profile(args):
    arts = load(journal=args.journal, yearFrom=args.yearFrom, yearTo=args.yearTo)
    if args.genre:
        arts = [a for a in arts if a.get("discipline") == args.genre]
    if args.topic:
        q = tokens(args.topic)
        arts = [a for a in arts if q & tokens((a.get("title") or "") + (a.get("abstract") or ""))]
    print(f"命中 {len(arts)} 篇")
    disc = collections.Counter(a.get("discipline") or "未标注" for a in arts)
    print("体裁分布: " + "  ".join(f"{k}:{v}" for k, v in disc.most_common()))
    abs_lens = [len(a.get("abstract") or "") for a in arts if a.get("abstract")]
    if abs_lens:
        abs_lens.sort()
        print(f"摘要字数: 中位数 {abs_lens[len(abs_lens)//2]}，区间 {abs_lens[0]}–{abs_lens[-1]}")
    kw = collections.Counter(k for a in arts for k in (a.get("keywords") or []))
    if kw:
        print("高频关键词 TOP15: " + "、".join(f"{k}({v})" for k, v in kw.most_common(15)))

def cmd_export(args):
    arts = load(journal=args.journal, yearFrom=args.yearFrom, yearTo=args.yearTo)
    fmt = args.format
    out = args.outFile or f"lawcorpus_export.{ 'csv' if fmt=='csv' else ('md' if fmt=='markdown' else 'jsonl')}"
    if os.path.exists(out):
        print(f"文件已存在，未覆盖: {out}（如需覆盖请先删除）")
        return
    if fmt == "jsonl":
        with open(out, "w", encoding="utf-8") as f:
            for a in arts:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
    elif fmt == "csv":
        import csv
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            cols = ["journal", "year", "issue", "title", "authors", "keywords"] + (["abstract"] if args.includeAbstract else [])
            w.writerow(cols)
            for a in arts:
                w.writerow([a.get("journal"), a.get("year"), a.get("issue"), a.get("title"),
                            "、".join(a.get("authors") or []), "、".join(a.get("keywords") or [])]
                           + ([a.get("abstract")] if args.includeAbstract else []))
    else:
        with open(out, "w", encoding="utf-8") as f:
            for a in arts:
                f.write(f"## {a.get('title')}\n- {a['journal']} {a['year']}年第{a.get('issue')}期 | {'、'.join(a.get('authors') or [])}\n")
                f.write(f"- 关键词: {'、'.join(a.get('keywords') or [])}\n")
                if args.includeAbstract and a.get("abstract"):
                    f.write(f"- 摘要: {a['abstract']}\n")
                if a.get("outline"):
                    f.write("- 目录:\n" + "\n".join(f"  - {h}" for h in a["outline"]) + "\n")
                f.write("\n")
    print(f"已导出 {len(arts)} 条 → {out}")

def main():
    p = argparse.ArgumentParser(description="lawcorpus 查询脚本")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--journal"); s.add_argument("--verbose", action="store_true"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("frame"); s.add_argument("--topic", required=True); s.add_argument("--journal"); s.add_argument("--genre"); s.add_argument("--limit", type=int, default=5); s.set_defaults(fn=cmd_frame)
    s = sub.add_parser("match"); s.add_argument("--abstract"); s.add_argument("--title"); s.add_argument("--keywords"); s.add_argument("--journal"); s.add_argument("--limit", type=int, default=5); s.set_defaults(fn=cmd_match)
    s = sub.add_parser("profile"); s.add_argument("--journal"); s.add_argument("--yearFrom", type=int); s.add_argument("--yearTo", type=int); s.add_argument("--genre"); s.add_argument("--topic"); s.set_defaults(fn=cmd_profile)
    s = sub.add_parser("export"); s.add_argument("--format", choices=["csv", "jsonl", "markdown"], default="csv"); s.add_argument("--journal"); s.add_argument("--yearFrom", type=int); s.add_argument("--yearTo", type=int); s.add_argument("--outFile"); s.add_argument("--includeAbstract", action="store_true"); s.set_defaults(fn=cmd_export)
    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
