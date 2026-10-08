from enterprise_knowledge_assistant.retrieval import initial_queries, retrieve_passages


def test_compound_question_keeps_each_document_topic():
    queries = initial_queries('把公司QA的開戶準備與市場報告的Robo-Advisor段落一起看，只備妥證件就等於完成投資適合性評估嗎？')
    assert any('公司QA的開戶準備' == q for q in queries)
    assert any('市場報告的Robo-Advisor段落' == q for q in queries)


def test_continued_section_query_recovers_missing_page_and_deduplicates():
    calls = []
    def search(query):
        calls.append(query)
        content = '實務議題與前瞻思考 (續)\n6 最後項' if len(calls) == 1 else '3 中間項'
        page = '7' if len(calls) == 1 else '5'
        return {'results': [{'document': {
            'name': 'projects/test/documents/report',
            'derivedStructData': {'title': '測試報告', 'link': 'gs://bucket/report.pdf',
                                  'extractive_segments': [{'pageNumber': page, 'content': content}]*2},
        }}]}
    results, trace = retrieve_passages('報告提出哪些六大面向？', search)
    assert len(trace) == 2
    assert calls[1] == '測試報告 實務議題與前瞻思考'
    info = results[0]['unstructuredDocumentInfo']
    assert {c['pageIdentifier'] for c in info['documentContexts']} == {'5', '7'}
    assert len(info['documentContexts']) == 2
    assert info['uri'] == 'gs://bucket/report.pdf'


def test_neighboring_segments_keep_their_own_pages_and_source():
    def search(query):
        return {'results': [{'document': {
            'name': 'projects/test/documents/report',
            'derivedStructData': {
                'title': '跨頁報告', 'link': 'gs://bucket/report.pdf',
                'extractive_segments': [{
                    'pageNumber': '5', 'content': '第二階段',
                    'previous_segments': [{'pageNumber': '4', 'content': '第一階段'}],
                    'next_segments': [
                        {'pageNumber': '6', 'content': '第三階段'},
                        {'pageNumber': '6', 'content': '第三階段'},
                    ],
                }],
            },
        }}]}

    results, _ = retrieve_passages('請說明流程', search)
    info = results[0]['unstructuredDocumentInfo']
    assert info['documentContexts'] == [
        {'pageIdentifier': '5', 'content': '第二階段'},
        {'pageIdentifier': '4', 'content': '第一階段'},
        {'pageIdentifier': '6', 'content': '第三階段'},
    ]
    assert info['uri'] == 'gs://bucket/report.pdf'


def test_neighbors_cannot_displace_direct_hits_at_context_limit():
    def search(query):
        return {'results': [{'document': {
            'name': 'projects/test/documents/report',
            'derivedStructData': {
                'link': 'gs://bucket/report.pdf',
                'extractive_segments': [
                    {'pageNumber': str(i), 'content': f'直接命中{i}',
                     'next_segments': [{'pageNumber': '99', 'content': f'相鄰{i}'}]}
                    for i in range(18)
                ],
            },
        }}]}

    results, _ = retrieve_passages('請說明內容', search)
    contexts = results[0]['unstructuredDocumentInfo']['documentContexts']
    assert len(contexts) == 18
    assert all(context['content'].startswith('直接命中') for context in contexts)
