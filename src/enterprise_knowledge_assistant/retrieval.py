"""Retrieve source passages using only the question and live search results."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable
from urllib.parse import unquote


def normalize(text: str) -> str:
    return unicodedata.normalize('NFKC', text).replace('臺', '台')


def initial_queries(question: str) -> list[str]:
    queries = [question]
    # Preserve each part of a compound question rather than searching only names.
    parts = re.split(r'[，,。；;]|一起看|就代表|就等於', question)
    if '與' in question or '同時參考' in question:
        for part in parts:
            for subject in re.split(r'與|以及', part):
                subject = subject.strip(' 把依與，,？?')
                if len(subject) >= 8 and subject not in question[-10:]:
                    queries.append(subject)
    if re.search(r'只是|不只是|只[是有]', question):
        before = re.split(r'只是|不只是', question)[0]
        subject = re.split(r'[，,]', before)[-1].strip(' 的依？?')
        if 2 <= len(subject) <= 30:
            queries.append(f'{subject} 定義 範疇')
    return list(dict.fromkeys(queries))[:4]


def retrieve_passages(question: str, search: Callable[[str], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []

    def collect(query: str, scoped_document: str = '') -> None:
        payload = search(query)
        trace.append({'query': query, 'scope': scoped_document, 'response': payload})
        for result in payload.get('results', []):
            doc = result.get('document', {})
            name = doc.get('name', '')
            if scoped_document and name != scoped_document:
                continue
            metadata = doc.get('derivedStructData', {})
            segments = metadata.get('extractive_segments', [])
            if not name or not segments:
                continue
            current = documents.setdefault(name, {
                'document': name, 'uri': metadata.get('link', ''),
                'title': metadata.get('title') or unquote(metadata.get('link', '')).rsplit('/', 1)[-1],
                'documentContexts': [],
            })
            seen = {(c['pageIdentifier'], c['content']) for c in current['documentContexts']}
            for segment in segments:
                content = segment.get('content', '').strip()
                page = str(segment.get('pageNumber', ''))
                if content and (page, content) not in seen:
                    current['documentContexts'].append({'pageIdentifier': page, 'content': content})
                    seen.add((page, content))

    for query in initial_queries(question):
        collect(query)

    # A continued section is a useful query derived from the retrieved document,
    # not from an answer key. It recovers list items that span pages.
    if re.search(r'哪些|哪[一二三四五六七八九十兩\d]+[個項大種]|主要階段|核心流程', question):
        expanded = 0
        for name, doc in list(documents.items()):
            headings = []
            for context in doc['documentContexts']:
                for line in normalize(context['content']).splitlines():
                    match = re.fullmatch(r'\s*(.{4,35}?)\s*[（(]續[）)]\s*', line)
                    if match:
                        headings.append(match.group(1).strip())
            for heading in dict.fromkeys(headings):
                collect(f'{doc["title"]} {heading}', name)
                expanded += 1
                if expanded >= 2:
                    break
            if expanded >= 2:
                break

    # Keep a bounded, diverse source set. Document/page identity accompanies
    # every supplied passage so the Answer API can cite the actual source.
    results = []
    total_chars = 0
    for doc in documents.values():
        contexts = []
        for context in doc['documentContexts'][:18]:
            if total_chars + len(context['content']) > 110_000:
                break
            contexts.append(context)
            total_chars += len(context['content'])
        if contexts:
            results.append({'unstructuredDocumentInfo': {**doc, 'documentContexts': contexts}})
        if len(results) >= 8:
            break
    return results, trace
