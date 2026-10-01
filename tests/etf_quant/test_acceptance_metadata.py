"""Offline checks for acceptance documentation/configuration repairs."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_one_shot_example_exposes_required_frozen_reference_binding():
    example = json.loads((ROOT / 'services/etf-quant-runner/one_shot.config.example.json').read_bytes())
    assert 'model_reference_snapshot' in example
    assert isinstance(example['model_reference_snapshot'], str)
    assert example['model_reference_snapshot'] == ''  # no machine-specific dataset path


def test_adapted_ui_preserves_the_complete_upstream_permission_notice():
    notice = ROOT / 'dashboard/licenses/shadcn-ui-MIT.txt'
    assert sha256(notice.read_bytes()).hexdigest() == '1564074e13439397221ffd522e2e504d56561994a23d371aa5e3ad43e4f5423f'
    text = (ROOT / 'dashboard/THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    assert 'licenses/shadcn-ui-MIT.txt' in text
    assert '| class-variance-authority 0.7.1 | Apache-2.0 |' in text
    assert '未为自有研究与代码授予统一许可证' in text
