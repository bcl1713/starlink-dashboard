"use strict";

module.exports = {
  names: ["MAX_LINES"],
  description: "Limit file length",
  tags: ["length"],
  function: function (params, onError) {
    const max = 300;
    const lineCount = params.lines.length;

    if (lineCount > max) {
      onError({
        lineNumber: 1,
        detail: `File has ${lineCount} lines (max ${max}).`,
      });
    }
  },
};
