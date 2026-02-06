"""
Cluster Ratio Enhancement Module

This module provides enhanced cluster ratio adjustment logic for immediate
response to user skips, implementing the requirement to "immediately update 
the engagement ratio to prioritize the preferred cluster."

Key Enhancement: When a user skips a recommendation, the system immediately
boosts the representation of alternative clusters to quickly converge on 
the user's optimal cluster alignment.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional

class ClusterRatioEnhancer:
    """
    Enhances the basic cluster ratio tracking with immediate skip response
    and dynamic ratio adjustment capabilities.
    """
    
    def __init__(self, recommender):
        """
        Initialize the enhancer with a reference to the main recommender.
        
        Args:
            recommender: UserRecommender instance to enhance
        """
        self.recommender = recommender
        
    def handle_immediate_skip_response(self, skipped_track_id: str, duration: float) -> Dict:
        """
        Immediately adjust cluster ratios when a user skips a track.
        
        This implements the requirement: "When the user skips a recommendation, 
        immediately update the engagement ratio to prioritize the preferred cluster."
        
        Strategy:
        1. Identify the cluster of the skipped track
        2. Find the most recently liked alternative cluster
        3. Boost the alternative cluster's representation in session_likes
        4. Return adjustment details for logging/debugging
        
        Args:
            skipped_track_id: ID of the skipped track
            duration: How long the track was played (should be < 5s for skip)
            
        Returns:
            Dict with adjustment details
        """
        adjustment_info = {
            "action": "skip_response",
            "skipped_track_id": skipped_track_id,
            "skipped_duration": duration,
            "pre_skip_ratios": self.recommender.get_current_cluster_ratios().copy(),
            "adjustments_made": []
        }
        
        # Get the skipped track's cluster
        skipped_track = self.recommender.track_map.get(skipped_track_id)
        if not skipped_track:
            adjustment_info["error"] = "Skipped track not found"
            return adjustment_info
            
        skipped_cluster = self.recommender._find_vector_cluster(skipped_track['vector'])
        adjustment_info["skipped_cluster"] = skipped_cluster
        
        # Find the most recently liked alternative cluster
        alternative_boost_vector = None
        alternative_cluster = None
        
        # Look through recent session likes for a different cluster
        for i in range(len(self.recommender.session_likes) - 1, -1, -1):
            like_vector = self.recommender.session_likes[i]
            like_cluster = self.recommender._find_vector_cluster(like_vector)
            
            if like_cluster != skipped_cluster:
                alternative_boost_vector = like_vector
                alternative_cluster = like_cluster
                break
        
        # Apply immediate ratio adjustment
        if alternative_boost_vector is not None:
            # Boost the alternative cluster by adding its vector representation
            # This immediately increases its probability in the next recommendation
            boost_count = self._calculate_boost_amount(skipped_cluster, alternative_cluster)
            
            for _ in range(boost_count):
                self.recommender.session_likes.append(alternative_boost_vector)
                
            adjustment_info["adjustments_made"].append({
                "type": "boost_alternative_cluster",
                "cluster_id": alternative_cluster,
                "boost_count": boost_count,
                "total_likes_after": len(self.recommender.session_likes)
            })
            
        # Additionally, we can dampen the skipped cluster's influence
        # by temporarily reducing its representation (but not removing entirely)
        dampening_applied = self._apply_cluster_dampening(skipped_cluster)
        if dampening_applied:
            adjustment_info["adjustments_made"].append({
                "type": "dampen_skipped_cluster", 
                "cluster_id": skipped_cluster,
                "method": "negative_reinforcement"
            })
        
        # Calculate new ratios
        adjustment_info["post_skip_ratios"] = self.recommender.get_current_cluster_ratios()
        adjustment_info["ratio_change"] = self._calculate_ratio_change(
            adjustment_info["pre_skip_ratios"],
            adjustment_info["post_skip_ratios"]
        )
        
        return adjustment_info
    
    def _calculate_boost_amount(self, skipped_cluster: int, alternative_cluster: int) -> int:
        """
        Calculate how much to boost the alternative cluster based on current ratios.
        
        The boost amount depends on:
        1. Current dominance of the skipped cluster
        2. Strength of the user's streak/confidence
        3. How much correction is needed for quick convergence
        
        Args:
            skipped_cluster: Cluster ID that was just skipped
            alternative_cluster: Cluster ID to boost
            
        Returns:
            Number of times to add the alternative cluster vector
        """
        current_ratios = self.recommender.get_current_cluster_ratios()
        skipped_ratio = current_ratios.get(skipped_cluster, 0)
        alternative_ratio = current_ratios.get(alternative_cluster, 0)
        
        # Base boost: 1-2 additions to shift balance
        base_boost = 1
        
        # If skipped cluster is dominant (>60%), apply stronger correction
        if skipped_ratio > 60:
            base_boost = 2
            
        # If we're in a strong streak (confidence is high), apply more aggressive correction
        if self.recommender.streak > 2:
            base_boost += 1
            
        # If the alternative cluster is significantly underrepresented, boost more
        ratio_imbalance = skipped_ratio - alternative_ratio
        if ratio_imbalance > 30:  # 30%+ imbalance
            base_boost += 1
            
        # Cap the boost to avoid overcorrection
        return min(base_boost, 3)
    
    def _apply_cluster_dampening(self, skipped_cluster: int) -> bool:
        """
        Apply dampening to the skipped cluster to reduce its future influence.
        
        This is more sophisticated than just removing vectors - we apply
        negative reinforcement that affects the user vector and bandit scores.
        
        Args:
            skipped_cluster: Cluster ID to dampen
            
        Returns:
            True if dampening was applied
        """
        # Apply negative reinforcement to bandit scores
        if skipped_cluster in self.recommender.cluster_scores:
            # Increase beta (negative evidence) for this cluster
            self.recommender.cluster_scores[skipped_cluster]['beta'] += 0.5
            
            # Slight decrease in alpha to show this wasn't a completely positive experience
            # but don't penalize too heavily (the user might like other songs from this cluster)
            alpha_penalty = 0.1
            current_alpha = self.recommender.cluster_scores[skipped_cluster]['alpha']
            self.recommender.cluster_scores[skipped_cluster]['alpha'] = max(
                1.0,  # Don't go below baseline prior
                current_alpha - alpha_penalty
            )
            
            return True
        
        return False
    
    def _calculate_ratio_change(self, pre_ratios: Dict, post_ratios: Dict) -> Dict:
        """Calculate the change in cluster ratios after adjustment."""
        changes = {}
        all_clusters = set(list(pre_ratios.keys()) + list(post_ratios.keys()))
        
        for cluster_id in all_clusters:
            pre_ratio = pre_ratios.get(cluster_id, 0)
            post_ratio = post_ratios.get(cluster_id, 0)
            change = post_ratio - pre_ratio
            
            if abs(change) > 0.1:  # Only report significant changes
                changes[cluster_id] = {
                    "from": pre_ratio,
                    "to": post_ratio, 
                    "change": change
                }
        
        return changes
    
    def suggest_optimal_next_cluster(self) -> Tuple[Optional[int], str]:
        """
        Suggest the optimal cluster for the next recommendation based on
        current ratios and user interaction patterns.
        
        This implements intelligent cluster selection that goes beyond
        simple random sampling to actively balance user preferences.
        
        Returns:
            Tuple of (cluster_id, justification_string)
        """
        current_ratios = self.recommender.get_current_cluster_ratios()
        
        if not current_ratios:
            return None, "No interaction history available"
        
        # Strategy 1: If there's a strong imbalance, suggest the underrepresented cluster
        max_cluster = max(current_ratios.items(), key=lambda x: x[1])
        min_cluster = min(current_ratios.items(), key=lambda x: x[1])
        
        imbalance = max_cluster[1] - min_cluster[1]
        
        if imbalance > 25:  # 25%+ imbalance
            return min_cluster[0], f"Rebalancing: {max_cluster[0]} at {max_cluster[1]:.1f}%, boosting {min_cluster[0]} at {min_cluster[1]:.1f}%"
        
        # Strategy 2: If ratios are balanced, use recent trajectory
        recent_interactions = self.recommender.session_likes[-3:] if len(self.recommender.session_likes) >= 3 else self.recommender.session_likes
        
        if recent_interactions:
            recent_clusters = [self.recommender._find_vector_cluster(v) for v in recent_interactions]
            most_recent_cluster = recent_clusters[-1]
            
            # If user has been consistent with one cluster recently, continue that trend
            if len(set(recent_clusters)) == 1:
                return most_recent_cluster, f"Continuing recent trend in cluster {most_recent_cluster}"
            
            # If user is exploring, suggest the most recently engaged alternative
            cluster_counts = {}
            for cid in recent_clusters:
                cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
            
            balanced_cluster = max(cluster_counts.items(), key=lambda x: x[1])
            return balanced_cluster[0], f"Following recent exploration pattern"
        
        # Strategy 3: Default to highest performing cluster
        return max_cluster[0], f"Defaulting to best performing cluster {max_cluster[0]} at {max_cluster[1]:.1f}%"
    
    def get_convergence_metrics(self) -> Dict:
        """
        Calculate metrics about how well the system is converging on
        the user's optimal cluster alignment.
        
        Returns:
            Dictionary with convergence metrics
        """
        current_ratios = self.recommender.get_current_cluster_ratios()
        
        if len(current_ratios) < 2:
            return {"status": "insufficient_data", "interactions": len(self.recommender.session_likes)}
        
        # Calculate ratio entropy (measure of distribution balance)
        ratios_array = np.array(list(current_ratios.values())) / 100.0  # Convert to probabilities
        entropy = -np.sum(ratios_array * np.log2(ratios_array + 1e-10))  # Add small epsilon to avoid log(0)
        max_entropy = np.log2(len(current_ratios))  # Maximum entropy for uniform distribution
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        # Calculate stability (how much ratios are changing)
        recent_changes = []
        if len(self.recommender.history) >= 2:
            # This would require tracking ratio history, which isn't implemented yet
            # For now, we'll use a simpler stability measure
            stability = 1.0 - (self.recommender.exploration_drift / 1.0)  # Higher drift = lower stability
        else:
            stability = 0.5  # Neutral stability for insufficient data
        
        # Calculate confidence based on streak and interaction count
        confidence = min(1.0, (self.recommender.streak * 0.1) + (len(self.recommender.session_likes) * 0.05))
        
        return {
            "status": "active",
            "total_interactions": len(self.recommender.session_likes),
            "cluster_count": len(current_ratios),
            "ratios": current_ratios,
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,  # 0 = perfectly balanced, 1 = completely concentrated
            "stability": stability,  # 0 = very unstable, 1 = very stable
            "confidence": confidence,  # 0 = no confidence, 1 = very confident
            "streak": self.recommender.streak,
            "exploration_drift": self.recommender.exploration_drift
        }


def integrate_ratio_enhancements(recommender_instance):
    """
    Factory function to integrate ratio enhancement capabilities 
    into an existing UserRecommender instance.
    
    Args:
        recommender_instance: UserRecommender to enhance
        
    Returns:
        ClusterRatioEnhancer instance bound to the recommender
    """
    enhancer = ClusterRatioEnhancer(recommender_instance)
    
    # Monkey-patch enhanced skip handling into the recommender
    original_feedback_internal = recommender_instance.feedback_internal
    
    def enhanced_feedback_internal(track_id, duration, liked, disliked, finished, total_duration=0):
        # Call original feedback processing
        original_feedback_internal(track_id, duration, liked, disliked, finished, total_duration)
        
        # Apply immediate skip response if this was a skip
        is_skip = duration < 5.0  # Same threshold as original logic
        if is_skip and not liked:
            adjustment_info = enhancer.handle_immediate_skip_response(track_id, duration)
            
            # Log the adjustment for debugging
            if adjustment_info.get("adjustments_made"):
                print(f"[RATIO_ENHANCEMENT] Skip response applied:")
                for adjustment in adjustment_info["adjustments_made"]:
                    print(f"  • {adjustment['type']}: Cluster {adjustment.get('cluster_id', 'N/A')}")
                
                ratio_changes = adjustment_info.get("ratio_change", {})
                if ratio_changes:
                    print(f"  • Ratio changes:")
                    for cluster_id, change_info in ratio_changes.items():
                        print(f"    Cluster {cluster_id}: {change_info['from']:.1f}% → {change_info['to']:.1f}% ({change_info['change']:+.1f}%)")
    
    # Replace the feedback method
    recommender_instance.feedback_internal = enhanced_feedback_internal
    
    # Add convenience methods to the recommender
    recommender_instance.get_ratio_enhancer = lambda: enhancer
    recommender_instance.get_convergence_metrics = enhancer.get_convergence_metrics
    recommender_instance.suggest_optimal_next_cluster = enhancer.suggest_optimal_next_cluster
    
    return enhancer


# Usage Example:
"""
# In server_user.py or wherever UserRecommender is instantiated:

from cluster_ratio_enhancements import integrate_ratio_enhancements

# Create recommender as usual
recommender = UserRecommender(user_id, collection_name=collection_name, youtube_mode=youtube_mode)

# Integrate enhancements
enhancer = integrate_ratio_enhancements(recommender)

# Now the recommender has enhanced skip response and additional methods:
# - recommender.get_convergence_metrics()
# - recommender.suggest_optimal_next_cluster()
# - Enhanced skip processing that immediately adjusts ratios
"""