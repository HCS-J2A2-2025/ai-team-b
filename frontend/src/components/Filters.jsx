// frontend/src/components/Filters.jsx
import { useState } from 'react';

export default function Filters({ filters, setFilters, onApply, loading }) {
  // ローカルで学科ごとの選択された学年を管理する
  const [selectedYears, setSelectedYears] = useState({ J: [], S: [], R: [] });

  const update = (k, v) => setFilters((prev) => ({ ...prev, [k]: v }));

  // 学科チェックボックスのトグル
  const toggleMajor = (major, checked) => {
    let next = filters.course_classes || [];
    if (checked) {
      if (!next.includes(major)) next = [...next, major];
    } else {
      next = next.filter((c) => c !== major);
      // 学科を外したら該当の学年選択をクリア
      setSelectedYears((prev) => ({ ...prev, [major]: [] }));
    }
    update('course_classes', next);
    // クラス番号プレフィックスを更新
    computeClassNos(next, selectedYears);
  };

  // 学年のトグル
  const toggleYear = (major, year, checked) => {
    setSelectedYears((prev) => {
      const arr = prev[major] || [];
      let nextArr;
      if (checked) {
        if (!arr.includes(year)) nextArr = [...arr, year];
        else nextArr = arr;
      } else {
        nextArr = arr.filter((y) => y !== year);
      }
      const updated = { ...prev, [major]: nextArr };
      // クラス番号プレフィックスを更新
      computeClassNos(filters.course_classes, updated);
      return updated;
    });
  };

  // クラス番号プレフィックス（class_nos）を計算して state に反映
  const computeClassNos = (majors, yearsObj) => {
    const prefixes = [];
    majors.forEach((m) => {
      const ys = yearsObj[m] || [];
      ys.forEach((y) => {
        prefixes.push((m + String(y)).toLowerCase());
      });
    });
    update('class_nos', prefixes);
  };

  return (
    <div style={{ border: '1px solid #ddd', padding: 12, borderRadius: 8 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>
          学年年度開始:
          <input
            type="number"
            value={filters.academic_year_start}
            onChange={(e) => update('academic_year_start', Number(e.target.value))}
            style={{ marginLeft: 8, width: 100 }}
          />
        </label>

        {/* 学科と学年選択 */}
        <div>
          学科:
          {['J', 'S', 'R'].map((major) => (
            <label key={major} style={{ marginLeft: 8 }}>
              <input
                type="checkbox"
                value={major}
                checked={filters.course_classes.includes(major)}
                onChange={(e) => toggleMajor(major, e.target.checked)}
              />
              {major}
            </label>
          ))}

          {/* 学年チェックボックス */}
          {filters.course_classes.includes('J') && (
            <span style={{ marginLeft: 8 }}>
              {['1', '2'].map((yr) => (
                <label key={`J${yr}`} style={{ marginLeft: 8 }}>
                  <input
                    type="checkbox"
                    value={`J${yr}`}
                    checked={selectedYears.J.includes(Number(yr))}
                    onChange={(e) => toggleYear('J', Number(yr), e.target.checked)}
                  />
                  J{yr}
                </label>
              ))}
            </span>
          )}
          {filters.course_classes.includes('S') && (
            <span style={{ marginLeft: 8 }}>
              {['2', '3'].map((yr) => (
                <label key={`S${yr}`} style={{ marginLeft: 8 }}>
                  <input
                    type="checkbox"
                    value={`S${yr}`}
                    checked={selectedYears.S.includes(Number(yr))}
                    onChange={(e) => toggleYear('S', Number(yr), e.target.checked)}
                  />
                  S{yr}
                </label>
              ))}
            </span>
          )}
          {filters.course_classes.includes('R') && (
            <span style={{ marginLeft: 8 }}>
              {['3', '4'].map((yr) => (
                <label key={`R${yr}`} style={{ marginLeft: 8 }}>
                  <input
                    type="checkbox"
                    value={`R${yr}`}
                    checked={selectedYears.R.includes(Number(yr))}
                    onChange={(e) => toggleYear('R', Number(yr), e.target.checked)}
                  />
                  R{yr}
                </label>
              ))}
            </span>
          )}
        </div>

        {/* 対象外（順調）も表示 */}
        <label style={{ marginLeft: 8 }}>
          順調のみ
          <input
            type="checkbox"
            checked={filters.include_excluded_good}
            onChange={(e) => update('include_excluded_good', e.target.checked)}
            style={{ marginLeft: 4 }}
          />
        </label>

        {/* 要フォローのみ */}
        <label style={{ marginLeft: 8 }}>
          要フォローのみ
          <input
            type="checkbox"
            checked={filters.only_followup_candidate}
            onChange={(e) => update('only_followup_candidate', e.target.checked)}
            style={{ marginLeft: 4 }}
          />
        </label>

        <button type="button" disabled={loading} onClick={onApply} style={{ marginLeft: 8 }}>
          反映
        </button>
      </div>
    </div>
  );
}
