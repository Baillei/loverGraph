def test_import_graph():
    from lover_graph.graph.lover_graph import build_graph

    g = build_graph()
    assert g is not None
