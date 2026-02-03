<script lang="ts">
  import { onMount } from 'svelte';
  import { get_api } from '../lib/api';
  
  // dashboard stats will be populated from API
  let stats = {
    totalMovies: 0,
    totalSeries: 0,
    candidatesForDeletion: 0,
    movieReclaimableSize: '0 GB',
    seriesReclaimableSize: '0 GB',
  };
  
  let loading = true;
  let error = '';

  async function fetchStats() {
    try {
      loading = true;
      error = '';
      const data = await get_api<any>('/api/dashboard');
      
      stats.totalMovies = data.data.stats.total_movies;
      stats.totalSeries = data.data.stats.total_series;
      stats.candidatesForDeletion = data.data.stats.deletion_candidates;
      stats.movieReclaimableSize = data.data.stats.movies_reclaimable_size_gb;
      stats.seriesReclaimableSize = data.data.stats.series_reclaimable_size_gb;
    } catch (err: any) {
      console.error('Error fetching dashboard stats:', err);
      error = err.message;
    } finally {
      loading = false;
    }
  }

  // fetch stats when component mounts
  onMount(() => {
    fetchStats();
  });

</script>

<div class="p-8">
  <div class="max-w-7xl mx-auto">
    <!-- header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-100 mb-2">Dashboard</h1>
      <p class="text-gray-400">Overview of your media library cleanup status</p>
    </div>

    <!-- stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
        <div class="text-gray-400 text-sm font-medium mb-1">Total Movies</div>
        <div class="text-3xl font-bold text-gray-100">{stats.totalMovies}</div>
      </div>

      <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
        <div class="text-gray-400 text-sm font-medium mb-1">Total Series</div>
        <div class="text-3xl font-bold text-gray-100">{stats.totalSeries}</div>
      </div>

      <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
        <div class="text-gray-400 text-sm font-medium mb-1">Candidates for Deletion</div>
        <div class="text-3xl font-bold text-yellow-500">{stats.candidatesForDeletion}</div>
      </div>

      <!-- <div class="card">
        <div class="text-gray-400 text-sm font-medium mb-1">Space to Reclaim</div>
        <div class="text-3xl font-bold text-green-500">{stats.spaceToReclaim}</div>
      </div> -->

      <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
        <div class="text-gray-400 text-sm font-medium mb-1">Space to Reclaim (Movies)</div>
        <div class="text-3xl font-bold text-green-500">{stats.movieReclaimableSize} GB</div>
      </div>

      <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
        <div class="text-gray-400 text-sm font-medium mb-1">Space to Reclaim (Series)</div>
        <div class="text-3xl font-bold text-green-500">{stats.seriesReclaimableSize} GB</div>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="bg-gray-900 rounded-lg border border-gray-800 p-6">
      <h2 class="text-xl font-bold text-gray-100 mb-4">Recent Activity</h2>
      <div class="text-gray-400 text-center py-8">
        No recent activity
      </div>
    </div>
  </div>
</div>
