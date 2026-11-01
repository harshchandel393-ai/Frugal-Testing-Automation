
(() => {

    const expectedHosts = new Set([
        "OUTER-SHELL",
        "MIDDLE-SHELL",
        "SEALED-PANEL"
    ]);

    const hosts = [];

    function traverse(root) {

        const walker = document.createTreeWalker(
            root,
            NodeFilter.SHOW_ELEMENT
        );

        let element;

        while ((element = walker.nextNode())) {

            if (expectedHosts.has(element.tagName)) {

                let boundary;

                if (element.shadowRoot) {
                    boundary = "OPEN";
                } else if (
                    element.tagName === "SEALED-PANEL"
                ) {
                    boundary = "CLOSED_BOUNDARY";
                } else {
                    boundary = "NOT_EXPOSED";
                }

                hosts.push({
                    tag: element.tagName,
                    dynamicClass: element.className,
                    rootAccess: boundary
                });
            }

            // Traverse only accessible open Shadow Roots.
            if (element.shadowRoot) {
                traverse(element.shadowRoot);
            }
        }
    }

    traverse(document);

    return {
        totalHosts: hosts.length,
        hosts: hosts,
        closedBoundaryDetected: hosts.some(
            host => host.rootAccess === "CLOSED_BOUNDARY"
        )
    };

})()
