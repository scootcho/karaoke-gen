import React from "react";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: { reviewerAction: string; finalText?: string; reasonCategory: string; reasonDetail?: string }) => void;
  suggestion?: { text: string; reasoning?: string; confidence?: number };
};

export const AIFeedbackModal: React.FC<Props> = ({ isOpen, onClose, onSubmit, suggestion }) => {
  const [reviewerAction, setAction] = React.useState("ACCEPT");
  const [finalText, setFinalText] = React.useState("");
  const [reasonCategory, setReason] = React.useState("AI_CORRECT");
  const [reasonDetail, setDetail] = React.useState("");

  if (!isOpen) return null;

  // Dark theme colors matching karaoke-gen
  const colors = {
    background: '#1a1a1a',    // slate-800
    text: '#f8fafc',          // slate-50
    textSecondary: '#888888', // slate-400
    border: '#2a2a2a',        // slate-700
    inputBg: '#0f0f0f',       // slate-900
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1300 }}>
      <div style={{ background: colors.background, padding: 16, width: 480, borderRadius: 8, border: `1px solid ${colors.border}`, color: colors.text }}>
        <h3 style={{ color: colors.text, margin: 0 }}>AI Suggestion</h3>
        <p style={{ marginTop: 8, color: colors.text }}>
          {suggestion?.text ?? "No suggestion"}
          {suggestion?.confidence != null ? ` (confidence ${Math.round((suggestion.confidence || 0) * 100)}%)` : null}
        </p>
        {suggestion?.reasoning ? <small style={{ color: colors.textSecondary }}>{suggestion.reasoning}</small> : null}

        <div style={{ marginTop: 12 }}>
          <label style={{ color: colors.text }}>Action</label>
          <select value={reviewerAction} onChange={(e) => setAction(e.target.value)} style={{ marginLeft: 8, background: colors.inputBg, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '4px 8px' }}>
            <option value="ACCEPT">Accept</option>
            <option value="REJECT">Reject</option>
            <option value="MODIFY">Modify</option>
          </select>
        </div>

        {reviewerAction === "MODIFY" ? (
          <div style={{ marginTop: 12 }}>
            <label style={{ color: colors.text }}>Final Text</label>
            <input value={finalText} onChange={(e) => setFinalText(e.target.value)} style={{ marginLeft: 8, width: "100%", background: colors.inputBg, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '4px 8px' }} />
          </div>
        ) : null}

        <div style={{ marginTop: 12 }}>
          <label style={{ color: colors.text }}>Reason</label>
          <select value={reasonCategory} onChange={(e) => setReason(e.target.value)} style={{ marginLeft: 8, background: colors.inputBg, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '4px 8px' }}>
            <option value="AI_CORRECT">AI_CORRECT</option>
            <option value="AI_INCORRECT">AI_INCORRECT</option>
            <option value="AI_SUBOPTIMAL">AI_SUBOPTIMAL</option>
            <option value="CONTEXT_NEEDED">CONTEXT_NEEDED</option>
            <option value="SUBJECTIVE_PREFERENCE">SUBJECTIVE_PREFERENCE</option>
          </select>
        </div>

        <div style={{ marginTop: 12 }}>
          <label style={{ color: colors.text }}>Details</label>
          <textarea value={reasonDetail} onChange={(e) => setDetail(e.target.value)} style={{ marginLeft: 8, width: "100%", background: colors.inputBg, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '4px 8px' }} />
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button onClick={onClose} style={{ background: colors.border, color: colors.text, border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer' }}>Cancel</button>
          <button
            onClick={() =>
              onSubmit({ reviewerAction, finalText: finalText || undefined, reasonCategory, reasonDetail: reasonDetail || undefined })
            }
            style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer' }}
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIFeedbackModal;


