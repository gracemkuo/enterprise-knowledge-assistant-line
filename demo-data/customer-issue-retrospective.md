# Northstar Labs — Customer Issue Retrospective

Date: 2026-07-08

During a customer import, an invalid column mapping caused repeated validation
errors. The team considered three options: adding more documentation, failing
the import immediately, or introducing a preview step that highlights invalid
columns before submission.

The team selected the preview step because documentation alone had not
prevented similar mistakes, while immediate failure did not explain how to fix
the mapping. The first version will display invalid columns and recommend the
closest valid field. Product will review error rates four weeks after release.

