import React from 'react';

interface SlideData {
    id: number;
    type: string;
    title: string;
    subtitle?: string;
    points?: string[];
    table?: string;
    fragment_b64?: string;
    theme: {
        primary: string;
        secondary: string;
        background: string;
        text: string;
        accent: string;
    };
}

interface SlidePreviewProps {
    slide: SlideData;
}

const SlidePreview: React.FC<SlidePreviewProps> = ({ slide }) => {
    const renderTable = (tableMd: string) => {
        const lines = tableMd.trim().split('\n');
        const rows = lines.filter(l => l.includes('|') && !l.match(/^[| \-:]+$/));

        return (
            <table className="slide-table-preview">
                <tbody>
                    {rows.map((row, idx) => (
                        <tr key={idx}>
                            {row.split('|').filter(c => c.trim() || row.split('|').length > 1).map((cell, cIdx) => (
                                <td key={cIdx}>{cell.trim()}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        );
    };

    const style = {
        backgroundColor: slide.theme.background,
        color: slide.theme.text,
        borderColor: slide.theme.accent
    };

    const renderContent = () => {
        switch (slide.type) {
            case 'title':
                return (
                    <div className="slide-content slide-type-title">
                        <div className="slide-title" style={{ color: slide.theme.primary }}>{slide.title}</div>
                        {slide.subtitle && <div className="slide-subtitle">{slide.subtitle}</div>}
                    </div>
                );
            case 'content':
                return (
                    <div className="slide-content">
                        <div className="slide-title" style={{ borderBottom: `2px solid ${slide.theme.primary}` }}>{slide.title}</div>
                        <div className="slide-points">
                            <ul>
                                {slide.points?.map((p, i) => <li key={i}>{p}</li>)}
                            </ul>
                        </div>
                        {slide.table && renderTable(slide.table)}
                        {slide.fragment_b64 && (
                            <img
                                src={`data:image/png;base64,${slide.fragment_b64}`}
                                alt="Element fragment"
                                className="slide-fragment-img"
                            />
                        )}
                    </div>
                );
            case 'conclusion':
                return (
                    <div className="slide-content">
                        <div className="slide-title" style={{ color: slide.theme.primary }}>{slide.title}</div>
                        <div className="slide-points">
                            <ul>
                                {slide.points?.map((p, i) => <li key={i}>{p}</li>)}
                            </ul>
                        </div>
                    </div>
                );
            case 'thankyou':
                return (
                    <div className="slide-content slide-type-thankyou">
                        <div className="slide-title">{slide.title}</div>
                        <div className="slide-subtitle" style={{ color: slide.theme.accent }}>{slide.subtitle}</div>
                    </div>
                );
            default:
                return null;
        }
    };

    return (
        <div className={`slide-card slide-type-${slide.type}`} style={style}>
            {renderContent()}
            <div style={{ position: 'absolute', bottom: '10px', right: '15px', fontSize: '10px', opacity: 0.5 }}>
                {slide.id + 1}
            </div>
        </div>
    );
};

export default SlidePreview;
