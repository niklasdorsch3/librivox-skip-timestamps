# Single flat JSON file for the Repository

`repository.json` is one flat file containing all books and chapters. Consumers download it and serve it from within their own application — it is not fetched at runtime from this repo.

The file will grow large as coverage expands (LibriVox has 15,000+ books). That is an acceptable trade-off: simplicity of distribution matters more than file size at this stage. Anyone consuming the data takes responsibility for how they serve it.

If the file becomes unmanageably large, the natural migration path is per-book files keyed by LibriVox project ID — but that decision is deferred until there is a concrete size problem.
