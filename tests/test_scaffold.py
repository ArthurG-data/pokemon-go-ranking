def test_package_imports():
    import pipeline

    assert pipeline.__doc__.startswith("Pokémon GO ranking pipeline")
