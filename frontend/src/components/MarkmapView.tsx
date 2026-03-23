import React, { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Markmap } from 'markmap-view';
import { Transformer } from 'markmap-lib';

interface MarkmapViewProps {
    markdown: string;
    className?: string;
    style?: React.CSSProperties;
}

export interface MarkmapViewHandle {
    fitView: () => void;
}

const transformer = new Transformer();

const MarkmapView = forwardRef<MarkmapViewHandle, MarkmapViewProps>(({ markdown, className, style }, ref) => {
    const svgRef = useRef<SVGSVGElement>(null);
    const mmRef = useRef<Markmap>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    useImperativeHandle(ref, () => ({
        fitView: () => {
            if (mmRef.current) {
                mmRef.current.fit();
            }
        }
    }));

    useEffect(() => {
        if (svgRef.current && !mmRef.current) {
            mmRef.current = Markmap.create(svgRef.current, {
                autoFit: true,
                paddingX: 32, // Increase padding for a more centered look
                duration: 500,
            });
        }

        if (mmRef.current) {
            const { root } = transformer.transform(markdown);
            mmRef.current.setData(root);

            // Initial fit with a small delay
            const timer = setTimeout(() => {
                mmRef.current?.fit();
            }, 200);

            return () => clearTimeout(timer);
        }
    }, [markdown]);

    // Handle resize to keep the map centered and filling the space
    useEffect(() => {
        if (!containerRef.current || !mmRef.current) return;

        const resizeObserver = new ResizeObserver(() => {
            mmRef.current?.fit();
        });

        resizeObserver.observe(containerRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    return (
        <div ref={containerRef} className={className} style={{ width: '100%', height: '100%', ...style }}>
            <svg ref={svgRef} className="markmap-svg" style={{ width: '100%', height: '100%' }} />
        </div>
    );
});

export default MarkmapView;
