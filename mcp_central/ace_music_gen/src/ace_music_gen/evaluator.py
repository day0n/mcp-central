"""音频质量评估器模块"""

import librosa
import numpy as np
from typing import Dict

try:
    from pesq import pesq
    HAS_PESQ = True
except ImportError:
    HAS_PESQ = False
    print("PESQ library not available, will use simplified audio analysis")


class AudioEvaluator:
    """音频质量评估器"""
    
    def __init__(self):
        self.has_pesq = HAS_PESQ
    
    def evaluate_audio(self, audio_path: str) -> Dict:
        """
        评估音频文件质量
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            评估结果字典
        """
        try:
            # 使用librosa加载音频
            y, sr = librosa.load(audio_path, sr=None)
            
            # 基础音频特征分析
            audio_features = self._analyze_audio_features(y, sr)
            
            # 质量评估
            quality_scores = self._calculate_quality_scores(y, sr)
            
            # 生成综合评估
            overall_score = self._calculate_overall_score(audio_features, quality_scores)
            
            # 生成建议
            recommendations = self._generate_recommendations(audio_features, quality_scores)
            
            return {
                "overall_score": float(overall_score),
                "audio_features": audio_features,
                "quality_scores": quality_scores,
                "recommendations": recommendations,
                "analysis_info": {
                    "duration": float(len(y) / sr),
                    "sample_rate": int(sr),
                    "channels": 1 if y.ndim == 1 else y.shape[0]
                }
            }
            
        except Exception as e:
            return {
                "error": f"音频分析失败: {str(e)}",
                "overall_score": 0.0
            }
    
    def _analyze_audio_features(self, y, sr):
        """分析音频特征"""
        features = {}

        # 频谱质心 (音色亮度)
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        features['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
        features['spectral_centroid_std'] = float(np.std(spectral_centroids))

        # RMS能量 (响度)
        rms = librosa.feature.rms(y=y)[0]
        features['rms_mean'] = float(np.mean(rms))
        features['rms_std'] = float(np.std(rms))

        # 零交叉率 (音频纯净度)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        features['zcr_mean'] = float(np.mean(zcr))

        # MFCC特征 (音色特征)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features['mfcc_mean'] = [float(x) for x in np.mean(mfccs, axis=1)]

        # 频谱对比度
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        features['spectral_contrast_mean'] = float(np.mean(spectral_contrast))

        return features
    
    def _calculate_quality_scores(self, y, sr):
        """计算音频质量分数"""
        scores = {}

        # 动态范围
        dynamic_range = np.max(y) - np.min(y)
        scores['dynamic_range'] = float(min(dynamic_range * 10, 10.0))  # 归一化到0-10

        # 信噪比估算
        rms = librosa.feature.rms(y=y)[0]
        snr_estimate = 20 * np.log10(np.mean(rms) / (np.std(rms) + 1e-10))
        scores['snr_estimate'] = float(min(max(snr_estimate / 10, 0), 10.0))  # 归一化到0-10

        # 频谱平衡度
        freqs = np.abs(np.fft.fft(y))
        freq_balance = 1.0 - np.std(freqs) / (np.mean(freqs) + 1e-10)
        scores['frequency_balance'] = float(min(max(freq_balance * 10, 0), 10.0))

        # 如果有PESQ，计算感知质量
        if self.has_pesq and sr == 16000:  # PESQ需要16kHz采样率
            try:
                # 对于单通道音频，与自身比较作为参考
                pesq_score = pesq(sr, y, y, 'wb')  # 宽带模式
                scores['pesq_score'] = float(pesq_score)
            except:
                scores['pesq_score'] = None
        else:
            scores['pesq_score'] = None

        return scores
    
    def _calculate_overall_score(self, features, scores):
        """计算综合评分"""
        total_score = 0
        count = 0
        
        # 动态范围权重: 30%
        if 'dynamic_range' in scores:
            total_score += scores['dynamic_range'] * 0.3
            count += 0.3
        
        # 信噪比权重: 25% 
        if 'snr_estimate' in scores:
            total_score += scores['snr_estimate'] * 0.25
            count += 0.25
            
        # 频谱平衡权重: 25%
        if 'frequency_balance' in scores:
            total_score += scores['frequency_balance'] * 0.25
            count += 0.25
            
        # PESQ分数权重: 20%
        if scores.get('pesq_score') is not None:
            pesq_normalized = min(scores['pesq_score'] / 4.5 * 10, 10.0)
            total_score += pesq_normalized * 0.2
            count += 0.2
            
        return float(total_score / count) if count > 0 else 5.0
    
    def _generate_recommendations(self, features, scores):
        """生成改进建议"""
        recommendations = []
        
        # 动态范围建议
        if scores.get('dynamic_range', 5) < 3:
            recommendations.append("动态范围较小，建议增强音频的响度变化")
        elif scores.get('dynamic_range', 5) > 8:
            recommendations.append("动态范围很好，音频层次丰富")
            
        # 信噪比建议
        if scores.get('snr_estimate', 5) < 3:
            recommendations.append("音频可能存在噪声问题，建议降噪处理")
        elif scores.get('snr_estimate', 5) > 7:
            recommendations.append("音频信噪比良好，声音清晰")
            
        # 频谱平衡建议
        if scores.get('frequency_balance', 5) < 4:
            recommendations.append("频谱分布不够均衡，建议调整EQ")
        elif scores.get('frequency_balance', 5) > 7:
            recommendations.append("频谱分布均衡，音色自然")
            
        # PESQ建议
        if scores.get('pesq_score'):
            if scores['pesq_score'] < 2.0:
                recommendations.append("感知音质较低，建议检查音频编码质量")
            elif scores['pesq_score'] > 3.5:
                recommendations.append("感知音质优秀")
        
        if not recommendations:
            recommendations.append("音频质量整体良好")
            
        return recommendations